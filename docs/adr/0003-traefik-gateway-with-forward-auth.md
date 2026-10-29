# ADR-0003: Traefik as API gateway with forwardAuth for JWT

**Status:** Accepted
**Deciders:** Project owner

## Context
job-service and user-service were each exposed on their own port, and `GET /jobs` was public. Clients had to know several addresses, and authentication logic existed only inside user-service. We want a single entry point, with internal services not reachable from outside, and JWT validation in one place.

## Decision
Use Traefik as the single entry point (port 80). Routes are declared as Docker labels on each service. Protected routes use the `forwardAuth` middleware, which calls `GET /auth/verify` on user-service before forwarding a request. Only user-service knows how to validate a JWT.

## Options Considered

### Option A: Traefik + forwardAuth
| Dimension | Assessment |
|---|---|
| Complexity | Medium (label syntax) |
| Cost | One extra container |
| Scalability | Good |
| Team familiarity | Low (new tool, chosen partly to learn it) |

**Pros:** routes live next to the service definition; new services need only labels; JWT logic stays in one service; built-in dashboard and Prometheus metrics.
**Cons:** labels are verbose and harder to debug than a config file; extra network hop per protected request; needs read access to the Docker socket.

### Option B: Nginx + auth_request
**Pros:** very well known, equally capable for this use case.
**Cons:** routes live in a central config file that must be edited and reloaded for every new service.

### Option C: Gateway written in FastAPI
**Pros:** full control, showcases coding skills.
**Cons:** re-implements proxying (timeouts, streaming, headers) that mature tools already handle.

### Option D: Each service validates JWT itself
**Pros:** no gateway needed, no extra hop.
**Cons:** the secret and validation logic are duplicated in every service; services stay publicly reachable.

## Trade-off Analysis
Options A and B are functionally equivalent here. Traefik was chosen because label-based, dynamic configuration fits Docker Compose well and is the same model Kubernetes Ingress uses. Writing a custom gateway was rejected as reinventing a solved problem.

## Consequences
- Easier: adding a service (labels only); one place to change authentication rules.
- Harder: debugging a wrong label; `/metrics`, `/health` and `/docs` are no longer reachable from outside unless routed on purpose.
- Security assumption: internal services trust that only Traefik can reach them, which holds only while their ports are not published.
- `/auth/verify` is stateless (signature and expiry only), so a token stays valid until it expires even if the user is deleted.
- To revisit: Docker socket exposure (use a socket proxy in production), `api.insecure` dashboard, TLS, rate limiting, and a database check in `/auth/verify` if immediate revocation is needed.
