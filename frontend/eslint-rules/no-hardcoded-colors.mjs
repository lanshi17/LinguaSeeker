/**
 * ESLint rule: no-hardcoded-colors
 *
 * Forbids hardcoded hex color values (#xxx, #xxxxxx, #xxxxxxxx) in JSX style
 * attributes and adjacent string positions. Use CSS variables (var(--color-*))
 * instead — see globals.css for the design token list.
 *
 * Allowed:
 *   style={{ color: "var(--color-text)" }}
 *   style={{ background: "linear-gradient(#0891b2, #0e7490)" }}
 *
 * Disallowed:
 *   style={{ color: "#111827" }}
 *   style={{ border: "1px solid #e5e7eb" }}
 *   <Tag style={{ ... }}> where value contains a hex color
 */

const HEX_COLOR = /#(?:[0-9a-fA-F]{3}){1,2}\b/;

/** Check if a node is a string literal inside a JSX style attribute value. */
function isInsideJsxStyleAttr(node, ancestors) {
  // Walk up from the node to find a JSXAttribute named "style".
  // ancestors[0] = root, ancestors[last] = immediate parent.
  let current = node;
  for (let i = ancestors.length - 1; i >= 0; i--) {
    const parent = ancestors[i];

    // Found a JSXAttribute whose value is our current subtree
    if (
      parent.type === "JSXAttribute" &&
      parent.name?.name === "style" &&
      parent.value === current
    ) {
      return true;
    }

    // Continue walking up for these node types that can be inside a style value
    if (
      parent.type === "Property" ||
      parent.type === "ObjectProperty" ||
      parent.type === "ObjectExpression" ||
      parent.type === "JSXExpressionContainer" ||
      parent.type === "ArrayExpression" ||
      parent.type === "ConditionalExpression" ||
      parent.type === "TemplateLiteral"
    ) {
      current = parent;
      continue;
    }

    // Hit something outside the style value tree
    if (parent.type === "JSXElement" || parent.type === "JSXFragment" || parent.type === "CallExpression") {
      return false;
    }

    // Default: stop
    return false;
  }
  return false;
}

/** @type {import('eslint').Rule.RuleModule} */
export default {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow hardcoded hex colors in JSX style attributes. Use CSS variables (var(--color-*)).",
    },
    messages: {
      hardcodedColor:
        "Hardcoded hex color '{{color}}' in style. Use a CSS variable from globals.css (e.g. var(--color-text)).",
    },
    schema: [],
  },

  create(context) {
    const sourceCode = context.sourceCode;

    function checkNode(node) {
      if (typeof node.value !== "string") return;
      if (!HEX_COLOR.test(node.value)) return;

      const ancestors = sourceCode.getAncestors(node);
      if (!isInsideJsxStyleAttr(node, ancestors)) return;

      const match = node.value.match(HEX_COLOR);
      context.report({
        node,
        messageId: "hardcodedColor",
        data: { color: match?.[0] ?? node.value },
      });
    }

    return {
      Literal(node) {
        checkNode(node);
      },

      TemplateLiteral(node) {
        const fullText = node.quasis.map((q) => q.value.raw).join("...");
        if (!HEX_COLOR.test(fullText)) return;

        const ancestors = sourceCode.getAncestors(node);
        if (!isInsideJsxStyleAttr(node, ancestors)) return;

        const match = fullText.match(HEX_COLOR);
        context.report({
          node,
          messageId: "hardcodedColor",
          data: { color: match?.[0] ?? "template" },
        });
      },
    };
  },
};
