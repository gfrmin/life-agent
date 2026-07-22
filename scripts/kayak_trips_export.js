/*
 * Kayak Trips full-history exporter.
 *
 * HOW TO RUN
 *   1. Log in to https://www.kayak.com/ in your browser.
 *   2. Navigate to https://www.kayak.com/trips  (must be on the kayak.com origin
 *      so the session cookies are sent same-origin).
 *   3. Open DevTools -> Console. Brave/Chromium may require you to type
 *      "allow pasting" and hit Enter once before it will accept a pasted script.
 *   4. Paste this whole file, hit Enter, wait. It logs progress and finally
 *      triggers a download of kayak-trips-export.json.
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

(async () => {
  // Set to true to additionally pull per-event order details and the parsed
  // source emails. Much slower and much chattier; leave false for a first pass.
  const DEEP = false;
  const DELAY_MS = 250; // be polite; raise if you start seeing 429s

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const getJSON = async (path) => {
    const res = await fetch(path, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
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

  console.log('Discovering trips...');

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
    console.error('No trip listing endpoint responded. Are you logged in on www.kayak.com?');
    return;
  }

  const tripIndex = listings.reduce(
    (acc, r) => collectTrips(r.data, acc),
    new Map(),
  );
  const tripIds = [...tripIndex.keys()];
  console.log(`Found ${tripIds.length} unique trips. Fetching details...`);

  const trips = [];
  for (const [i, tripId] of tripIds.entries()) {
    console.log(`[${i + 1}/${tripIds.length}] ${tripId}`);

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

  console.log(`Done. Exported ${trips.length} trips.`);
  window.__kayakExport = payload; // also left in memory for poking at
})();
