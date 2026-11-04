FROM python:3.12-slim-bookworm AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /opt/iopsych
RUN python -m venv /opt/venv
COPY packages/shared/python packages/shared/python
COPY apps/api/requirements.txt apps/api/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r apps/api/requirements.txt

FROM python:3.12-slim-bookworm AS runtime
ARG REVISION=unknown
LABEL org.opencontainers.image.revision=$REVISION
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
WORKDIR /opt/iopsych
COPY --from=build /opt/venv /opt/venv
# Keep the editable shared-library path and monorepo-relative definition paths.
COPY --from=build /opt/iopsych/packages/shared/python packages/shared/python
COPY packages/shared/definitions packages/shared/definitions
COPY packages/shared/schemas packages/shared/schemas
COPY apps/api/app apps/api/app
COPY apps/api/alembic apps/api/alembic
COPY apps/api/alembic.ini apps/api/alembic.ini
WORKDIR /opt/iopsych/apps/api
USER 10001:10001
EXPOSE 8000
STOPSIGNAL SIGTERM
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--timeout-graceful-shutdown", "25"]
