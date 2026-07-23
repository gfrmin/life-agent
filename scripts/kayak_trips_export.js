/*
 * Kayak Trips full-history exporter.
 *
 * HOW TO RUN
 *   1. Log in to https://www.kayak.com/ in your browser.
 *   2. Navigate to https://www.kayak.com/trips  (must be on the kayak.com origin
 *      so the session cookies are sent same-origin).
 *   3. Open DevTools -> Console. Brave/Chromium may require you to type
 *      "allow pasting" and hit Enter once before it will accept a pasted script.
 *   4. Paste this whole file, hit Enter. It installs a CSRF interceptor and then
 *      waits for the page to make an API call of its own -- click a trip, or
 *      switch tabs, and the export starts automatically.
 *   5. It finishes by downloading kayak-trips-export.json.
 *
 * WHY THE INTERCEPTOR
 *   These endpoints reject any request without an `X-CSRF` header
 *   (INVALID_FORM_TOKEN). The token is not in cookies, localStorage,
 *   sessionStorage, or meta tags -- it lives only in the app's JS memory. So
 *   rather than digging it out of a minified bundle, we wrap fetch/XHR and
 *   lift the token off the page's own outgoing requests. The token stays in
 *   the browser: it is never printed, pasted, or written to disk.
 *
 * PROGRESS REPORTING
 *   Progress goes to document.title as well as the console, because a console
 *   log-level filter can silently swallow console.log while still echoing
 *   results -- which looks exactly like a hung script. Watch the tab title.
 *
 * Endpoints used (recovered from Kayak's own frontend bundle; each verified to
 * exist by returning 401 INVALID_SESSION when unauthenticated, whereas a bogus
 * path returns 404 NOT_FOUND):
 *   GET /i/api/trips/trip/v3/allTrips?type=owned|shared|bookedForGuest
 *   GET /i/api/trips/trip/v2/allTrips                      (older, no type param)
 *   GET /i/api/trips/trip/v1/{tripId}                      (trip detail)
 *   GET /i/api/trips/event/v1/allEvents/{tripId}           (all events in a trip)
 *   GET /i/api/trips/event/v1/{eventId}/allOrderDetails    (optional, see DEEP)
 *   GET /i/api/trips/event/v1/{eventId}/allParsedEmails    (optional, see DEEP)
 */

// --- CSRF interceptor -------------------------------------------------------
// Installed at top level, synchronously, so it is capturing before anything
// below awaits. Idempotent: re-pasting the script will not double-wrap.
if (!window.__kayakCsrfHook) {
  window.__kayakCsrfHook = true;
  window.__csrf = window.__csrf || null;
  const origFetch = window.fetch;
  window.fetch = function (...a) {
    const h = new Headers(
      a[1]?.headers || (a[0] instanceof Request ? a[0].headers : undefined),
    );
    const t = h.get('X-CSRF') || h.get('x-csrf');
    if (t) window.__csrf = t;
    return origFetch.apply(this, a);
  };
  const origSet = XMLHttpRequest.prototype.setRequestHeader;
  XMLHttpRequest.prototype.setRequestHeader = function (k, v) {
    if (/^x-csrf$/i.test(k)) window.__csrf = v;
    return origSet.apply(this, arguments);
  };
}

(async () => {
  // Set to true to additionally pull per-event order details and the parsed
  // source emails. Much slower and much chattier. NOTE: a DEEP run on this
  // account returned null for allParsedEmails/allOrderDetails on 260/260 events
  // — Kayak does not expose the source emails via the API — so DEEP buys nothing
  // here; leave false. Kept as a switch in case another account behaves differently.
  const DEEP = false;
  const DELAY_MS = 250; // be polite; raise if you start seeing 429s
  const TIMEOUT_MS = 20000; // no request may hang the whole run

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // Progress goes to the tab title too -- see PROGRESS REPORTING in the header.
  const origTitle = document.title;
  const say = (msg) => {
    document.title = msg;
    console.log(msg);
  };

  // Wait for the page to make an API call we can lift a token from. Nudge the
  // user rather than failing: they just have to click something.
  if (!window.__csrf) {
    say('Waiting for CSRF token -- click a trip or switch tabs...');
    const deadline = Date.now() + 120000;
    while (!window.__csrf && Date.now() < deadline) await sleep(500);
    if (!window.__csrf) {
      document.title = origTitle;
      console.error(
        'No X-CSRF token seen in 2 minutes. Re-run this script, then interact ' +
          'with the Trips UI so the page issues an API request.',
      );
      return;
    }
  }
  say('Got CSRF token. Starting export...');

  const getJSON = async (path) => {
    // Token is read fresh on every call: if the app rotates it mid-run, we pick
    // up the new one instead of failing the rest of the export.
    const res = await fetch(path, {
      credentials: 'include',
      headers: { Accept: 'application/json', 'X-CSRF': window.__csrf },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} @ ${path}`);
    return res.json();
  };

  const attempt = async (path) => {
    try {
      return { ok: true, path, data: await getJSON(path) };
    } catch (err) {
      console.warn('  skip', path, '-', err.message);
      return { ok: false, path, error: String(err.message) };
    }
  };

  // The exact envelope shape of allTrips is not documented, so rather than
  // guessing a key we walk the whole response and collect anything that looks
  // like a trip (an object carrying a tripId).
  const collectTrips = (node, found = new Map()) => {
    if (Array.isArray(node)) {
      node.forEach((n) => collectTrips(n, found));
    } else if (node && typeof node === 'object') {
      if (typeof node.tripId === 'string' && !found.has(node.tripId)) {
        found.set(node.tripId, node);
      }
      Object.values(node).forEach((v) => collectTrips(v, found));
    }
    return found;
  };

  const collectEventIds = (node, found = new Set()) => {
    if (Array.isArray(node)) {
      node.forEach((n) => collectEventIds(n, found));
    } else if (node && typeof node === 'object') {
      if (typeof node.eventId === 'string') found.add(node.eventId);
      Object.values(node).forEach((v) => collectEventIds(v, found));
    }
    return found;
  };

  say('Discovering trips...');

  const listPaths = [
    '/i/api/trips/trip/v3/allTrips?type=owned',
    '/i/api/trips/trip/v3/allTrips?type=shared',
    '/i/api/trips/trip/v3/allTrips?type=bookedForGuest',
    '/i/api/trips/trip/v2/allTrips',
  ];

  const listings = [];
  for (const p of listPaths) {
    const r = await attempt(p);
    if (r.ok) {
      const n = collectTrips(r.data).size;
      console.log(`  ${p} -> ${n} trip id(s)`);
      listings.push(r);
    }
    await sleep(DELAY_MS);
  }

  if (!listings.length) {
    document.title = origTitle;
    console.error('No trip listing endpoint responded. Are you logged in on www.kayak.com?');
    return;
  }

  const tripIndex = listings.reduce(
    (acc, r) => collectTrips(r.data, acc),
    new Map(),
  );
  const tripIds = [...tripIndex.keys()];
  say(`Found ${tripIds.length} unique trips. Fetching details...`);

  const trips = [];
  for (const [i, tripId] of tripIds.entries()) {
    say(`[${i + 1}/${tripIds.length}] fetching trips...`);

    const detail = await attempt(`/i/api/trips/trip/v1/${tripId}`);
    await sleep(DELAY_MS);
    const events = await attempt(`/i/api/trips/event/v1/allEvents/${tripId}`);
    await sleep(DELAY_MS);

    const record = {
      tripId,
      summary: tripIndex.get(tripId),
      detail: detail.ok ? detail.data : { error: detail.error },
      events: events.ok ? events.data : { error: events.error },
    };

    if (DEEP && events.ok) {
      record.eventExtras = {};
      for (const eventId of collectEventIds(events.data)) {
        const [orders, emails] = [
          await attempt(`/i/api/trips/event/v1/${eventId}/allOrderDetails`),
          await attempt(`/i/api/trips/event/v1/${eventId}/allParsedEmails`),
        ];
        record.eventExtras[eventId] = {
          orderDetails: orders.ok ? orders.data : null,
          parsedEmails: emails.ok ? emails.data : null,
        };
        await sleep(DELAY_MS);
      }
    }

    trips.push(record);
  }

  const payload = {
    exportedAt: new Date().toISOString(),
    tripCount: trips.length,
    rawListings: listings.map(({ path, data }) => ({ path, data })),
    trips,
  };

  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), {
    href: url,
    download: 'kayak-trips-export.json',
  });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);

  document.title = origTitle;
  console.log(`Done. Exported ${trips.length} trips.`);
  window.__kayakExport = payload; // also left in memory for poking at
  return `Done. Exported ${trips.length} trips.`; // echoed even if logs are filtered
})();
