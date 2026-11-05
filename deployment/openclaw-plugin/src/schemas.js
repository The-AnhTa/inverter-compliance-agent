import inputSchemaDocument from "../schemas/assess_inverter_configuration.input.schema.json" with { type: "json" };
import outputSchemaDocument from "../schemas/assess_inverter_configuration.output.schema.json" with { type: "json" };

function loadSchema(schema) {
  const root = structuredClone(schema);

  function resolve(value) {
    if (Array.isArray(value)) {
      return value.map(resolve);
    }
    if (!value || typeof value !== "object") {
      return value;
    }
    if (typeof value.$ref === "string" && value.$ref.startsWith("#/$defs/")) {
      const key = value.$ref.slice("#/$defs/".length);
      const target = root.$defs?.[key];
      if (!target) {
        throw new Error(`Unresolved local schema reference: ${value.$ref}`);
      }
      const siblings = Object.fromEntries(Object.entries(value).filter(([name]) => name !== "$ref"));
      return resolve({ ...structuredClone(target), ...siblings });
    }
    return Object.fromEntries(
      Object.entries(value)
        .filter(([name]) => !["$schema", "$id", "$defs", "title"].includes(name))
        .map(([name, child]) => [name, resolve(child)]),
    );
  }

  return resolve(root);
}

export const inputSchema = loadSchema(inputSchemaDocument);
export const outputSchema = loadSchema(outputSchemaDocument);
