from pkm.policy import Allow, RequireApproval


def sensitive_doc_gate(transform_decl, sources, estimated_cost, context):
    config = context.policy_config.get("sensitive_doc_gate", {})
    sensitive_tags = set(config.get("tags", ["sensitive"]))
    for source in sources:
        if source.tags & sensitive_tags:
            return RequireApproval(
                reason=f"sensitive source {source.source_id[:12]}..."
            )
    return Allow()
