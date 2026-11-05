import { defineToolPlugin } from "openclaw/plugin-sdk/tool-plugin";
import { inputSchema, outputSchema } from "./schemas.js";
import { runAssessment } from "./runtime.js";


export default defineToolPlugin({
  id: "inverter-compliance-tool",
  name: "Inverter Compliance Tool",
  description: "Run the fixed synthetic-only deterministic inverter configuration assessment.",
  activation: { onStartup: true },
  tools: (tool) => [
    tool({
      name: "assess_inverter_configuration",
      label: "Assess synthetic inverter configuration",
      description:
        "Evaluate explicitly synthetic normalized inverter observations with the fixed local six-rule Python engine. This tool cannot access Android, a real inverter, the network, arbitrary files, or caller-selected commands.",
      parameters: inputSchema,
      outputSchema,
      optional: true,
      async execute(params, _config, context) {
        return await runAssessment(params, undefined, undefined, context.signal);
      },
    }),
  ],
});
