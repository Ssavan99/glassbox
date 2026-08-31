import { Navigate, useParams } from "react-router-dom";
import { ComingSoon } from "../components/ComingSoon";
import { ARCHITECTURES } from "../lib/architectures";
import type { ArchitectureId } from "../lib/types";
import { ARCHITECTURE_IDS } from "../lib/types";

function isArchitectureId(value: string | undefined): value is ArchitectureId {
  return !!value && (ARCHITECTURE_IDS as readonly string[]).includes(value);
}

export function Tutorial() {
  const { arch } = useParams<{ arch: string }>();

  if (!isArchitectureId(arch)) {
    return <Navigate to="/404" replace />;
  }

  const meta = ARCHITECTURES[arch];

  return (
    <ComingSoon
      title={`${meta.name} — tutorial`}
      phase="Phase 9"
      description={`${meta.tagline} The full tutorial page — how it works, when it wins, when it loses, and its real implementing code — lands in Phase 9.`}
    />
  );
}
