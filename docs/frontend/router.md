# Router

Vue Router configuration with authentication guards.

## Routes

| Path | Component | Auth Required | Description |
|------|-----------|---------------|-------------|
| `/` | `LoginView` | No | Login/join page |
| `/home` | `HomeView` | Yes | Main game dashboard |
| `/about` | `AboutView` | No | About page |
| `/config` | `ConfigView` | Yes | Configuration page |
| `/rulebook` | `RulebookView` | Yes | Rulebook browser |
| `/timeline` | `TimelineView` | Yes | Timeline viewer |

## Auth Guard

The `requiresAuth` meta field triggers a navigation guard that validates the session by calling `checkPlayerExists` on the backend. If validation fails, the user is redirected to `/`.
