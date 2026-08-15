# Stage 1 Assessment

## 1. Current pages/routes

- `/` overview, `/context-graph`, `/claims`, `/claims/[claimId]`
- `/advisor` agent home
- `/advisor/customers`
- `/advisor/customers/[customerId]`
- `/advisor/customers/[customerId]/briefing`
- `/advisor/customers/[customerId]/conversations/new`
- `/advisor/customers/[customerId]/memory`

## 2. Existing reusable components

- `components/Sidebar.tsx`
- Shared service clients in `frontend_v3/services`
- Repeated local card/table/list patterns inside advisor pages

## 3. Existing customer functionality

- Customer list with search and priority filter
- Customer 360 with profile, family, goals, needs, policies, claims, events, and conversations
- Deterministic priority signals from life events, concerns, and last contact
- Customer memory timeline and approval workflow

## 4. Existing AI functionality

- Gemini meeting briefing synthesis over retrieved context
- Gemini transcript summarization and memory extraction
- Advisor approval before extracted facts become customer truth

## 5. Existing Neo4j/Qdrant/Gemini integration

- Neo4j stores customer relationship facts and approved customer truth
- Qdrant stores embedded conversation/document memory and retrieves relevant snippets
- Gemini reasons over retrieved facts and proposes extracted memories
- DuckDB remains the structured policy/claims source

## 6. What should be retained

- Existing customer retrieval and prioritization logic
- Customer 360 and prepare-for-meeting workflow
- Conversation upload, semantic chunk storage, extraction, and memory approval
- Source/provenance fields on graph facts and briefing evidence

## 7. What should be changed

- Reframe the UI from proof-of-concept beta to advisor-facing SaaS
- Expand navigation to My Day, Customers, Conversations, Tasks, Connections, and Settings
- Add first-time onboarding
- Separate backend service boundaries by product responsibility
- Keep integrations as a connection framework until real provider implementations exist
