# Execution Log

- Task: Disable browser password autofill/suggestions on Host settings password field
- Category: adaptation
- Started: 20260907_113129
- Pipeline: 03-implement -> 07-review

## 03-implement

- Status: completed
- Goal: Password (and paired username) inputs on `/settings/host` must not receive browser autofill or password-manager suggestions; user types credentials manually.
- Scope: `agent-canvas/src/routes/host-settings.tsx`, `agent-canvas/__tests__/routes/host-settings-credentials.test.tsx`
- Changes:
  - Password/username start `readOnly` until the user focuses that field (immediate DOM unlock + React state).
  - Per-field unlock so focusing username does not unlock password for autofill.
  - Extra password-manager ignore attrs (`data-bwignore`, `data-form-type`) and non-login `name`s.
  - Reset unlock state when switching/creating hosts.
  - Test asserts initial `readonly` + unlock on click.
- Verification: `npm run test -- __tests__/routes/host-settings-credentials.test.tsx` — 2 passed.

## 05-fix (crash follow-up)

- Status: completed
- React #310 cause: `pickerHosts` `useMemo` ran after `meLoading` early return, so hook count grew when loading finished.
- Fix: hoist `pickerHosts` above early returns; remove readOnly unlock state machine; keep `type="text"` + CSS disc mask for Password Manager.
- Verification: credentials tests pass (2). more-menu failures are pre-existing (details panel needs pencil click).


