/* BSM's OpenAPI extension stays machine-readable; Swagger renders it as a policy. */
function SwaggerAccessPlugin(system) {
  const React = system.React;
  const h = React.createElement;
  let factorCode = "";
  let resetFactor = () => {};
  const labels = {
    public: "Public endpoint",
    authenticated: "Sign-in required",
    permission: "Permission required",
    "legacy-role": "Role restriction",
    custom: "Contextual access",
    unknown: "Access unknown",
  };
  const strings = (value) =>
    Array.isArray(value)
      ? [...new Set(value.filter((item) => typeof item === "string"))].sort()
      : [];
  const chips = (values) =>
    h(
      "ul",
      { className: "bsm-doc-chips" },
      values.map((value) => h("li", { key: value }, h("code", null, value))),
    );
  const fact = (label, value) =>
    h("div", { key: label }, h("dt", null, label), h("dd", null, value));
  function AccessPolicy({ policy }) {
    const required = strings(policy.required_permissions);
    const roles = strings(policy.allowed_roles);
    const checks = strings(policy.additional_checks);
    const scope = {
      server: "One server",
      collection: "Filtered server collection",
      global: "Global or account",
    }[policy.resource_scope];
    return h(
      "section",
      { className: "bsm-doc-access", "aria-label": "Operation access policy" },
      h(
        "div",
        { className: "bsm-doc-access-heading" },
        h("h4", null, "Access policy"),
        h(
          "span",
          { className: "bsm-doc-kind" },
          labels[policy.classification] || labels.unknown,
        ),
      ),
      h(
        "dl",
        null,
        fact(
          "Required capabilities",
          required.length
            ? chips(required)
            : policy.classification === "public"
              ? "None"
              : "Not declared",
        ),
        roles.length > 0 && fact("Allowed roles", chips(roles)),
        fact(
          "Authentication",
          {
            required: "Sign-in required",
            optional: "Optional",
            none: "Not required",
          }[policy.authentication] || "Not specified",
        ),
        scope && fact("Resource scope", scope),
        policy.integration_tokens &&
          fact(
            "Integration credentials",
            policy.integration_tokens === "supported"
              ? "Supported within their granted access"
              : "Not supported",
          ),
        checks.length > 0 && fact("Additional checks", chips(checks)),
      ),
      h(
        "p",
        { className: "bsm-doc-note" },
        policy.classification === "public"
          ? "This endpoint does not require a signed-in account."
          : "Role and capability requirements describe the policy. Server assignments, ownership, and operation checks still apply.",
      ),
      h(
        "details",
        null,
        h("summary", null, "Raw access metadata"),
        h("pre", null, JSON.stringify(policy, null, 2)),
      ),
    );
  }
  return {
    fn: {
      consumeAuthenticatorCode: () => {
        const code = factorCode;
        factorCode = "";
        resetFactor();
        return code;
      },
    },
    wrapComponents: {
      oauth2: (Original) =>
        function PasswordFactor(props) {
          const [value, setValue] = React.useState("");
          React.useEffect(() => {
            resetFactor = () => setValue("");
            return () => {
              factorCode = "";
              resetFactor = () => {};
            };
          }, []);
          return h(
            React.Fragment,
            null,
            h(Original, props),
            h(
              "label",
              { className: "bsm-doc-factor" },
              "Authenticator or recovery code",
              h("input", {
                value,
                autoComplete: "one-time-code",
                maxLength: 128,
                placeholder: "Only if two-factor authentication is enabled",
                onChange: (event) => {
                  factorCode = event.target.value;
                  setValue(event.target.value);
                },
              }),
            ),
          );
        },
      OperationExt: (Original) =>
        function OperationExtensions(props) {
          const raw = props.extensions?.get("x-bsm-access");
          const policy = raw?.toJS ? raw.toJS() : raw;
          if (!policy || typeof policy !== "object" || Array.isArray(policy))
            return h(Original, props);
          const remaining = props.extensions.delete("x-bsm-access");
          return h(
            React.Fragment,
            null,
            h(AccessPolicy, { policy }),
            remaining.size > 0 &&
              h(Original, { ...props, extensions: remaining }),
          );
        },
    },
  };
}
