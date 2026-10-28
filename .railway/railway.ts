// The web client's Railway project, as code (replaces railway.json, retired by Railway on 2026-12-01).
// Preview with `railway config plan` and apply with `railway config apply`; web/README.md has the details.
// Variables are preserve(): their values stay as set in Railway and never appear here.
import { bucket, defineRailway, github, postgres, preserve, project, service, volume } from "railway/iac";

export default defineRailway(() => {
  const harmonicfitness = github("RNCDev/harmonicfitness", { checkSuites: false });

  const Postgres = postgres("Postgres", { region: "us-east4-eqdc4a" });
  Postgres.networking = { privateNetworkEndpoint: "postgres" };
  const postgresVolume = volume("postgres-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "us-east4-eqdc4a", sizeMB: 5000 });
  const media = bucket("media", { region: "iad" });

  // One image (the root Dockerfile) runs as both services; HARMONICFITNESS_ROLE tells them apart.
  const build = { builder: "DOCKERFILE" as const, dockerfilePath: "Dockerfile" };
  const web = service("web", {
    source: harmonicfitness,
    build,
    deploy: { restartPolicyType: "ON_FAILURE", healthcheckPath: "/healthz" },
    replicas: { "us-east4-eqdc4a": 1 },
    env: { DATABASE_URL: preserve(), HARMONICFITNESS_BASE_URL: preserve(), HARMONICFITNESS_MASTER_KEY: preserve(), HARMONICFITNESS_PROVIDERS: preserve(), HARMONICFITNESS_ROLE: preserve(), PORT: preserve() },
  });
  const worker = service("worker", {
    source: harmonicfitness,
    build,
    deploy: { restartPolicyType: "ON_FAILURE" },
    replicas: { "us-east4-eqdc4a": 1 },
    env: { DATABASE_URL: preserve(), HARMONICFITNESS_BASE_URL: preserve(), HARMONICFITNESS_MASTER_KEY: preserve(), HARMONICFITNESS_PROVIDERS: preserve(), HARMONICFITNESS_ROLE: preserve() },
  });

  return project("harmonicFitness", {
    resources: [web, Postgres, worker, postgresVolume, media],
  });
});
