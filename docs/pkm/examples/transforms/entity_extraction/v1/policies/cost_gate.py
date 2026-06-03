from pkm.policy import Allow, Block


def cost_gate(transform_decl, sources, estimated_cost, context):
    config = context.policy_config.get("cost_gate", {})
    budget = config.get("budget_per_invocation_usd", 5.00)
    if estimated_cost.total_usd > budget:
        return Block(
            reason=f"cost ${estimated_cost.total_usd:.2f} > budget ${budget:.2f}"
        )
    return Allow()
