# Security policy

## Reporting

Do not open a public issue containing credentials, private Discord content,
hidden benchmark labels, confirmation receipts, or exploitable authorization
details. Contact the repository owner privately through GitHub instead.

## Supported surface

The maintained product is `products/dist-ui` on the default branch.

## Security invariants

- The browser receives sanitized events only.
- Production Discord writes require separate explicit authorization.
- Hidden evaluation labels never enter candidate context.
- Provider tokens, Discord tokens, API keys, and wallet material are never
  committed.
- Model candidates cannot promote themselves or change evaluator policy.
