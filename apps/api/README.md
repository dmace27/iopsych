# IOPsych API

The API is a Python 3.12+ FastAPI application. From the repository root, install
its dependencies with `npm run api:install`, start it with `npm run dev:api`,
and run its tests with `npm run test:api`.

Interactive OpenAPI documentation is available at <http://localhost:8000/docs>
while the service is running.

Database models live in `app/database`, and the schema is managed exclusively
through Alembic. From the repository root, use `npm run db:migrate`,
`npm run db:seed`, and `npm run db:verify`. The verification command checks that
the two synthetic seed organizations cannot read one another's users, roles,
profiles, or audit data through the organization-scoped access layer.
