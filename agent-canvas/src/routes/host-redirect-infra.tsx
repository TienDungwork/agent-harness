import { Navigate, useParams, useSearchParams } from "react-router";

/** Legacy /admin/infra → Settings → Host */
export default function HostRedirectInfra() {
  const [params] = useSearchParams();
  const q = new URLSearchParams();
  const fromQuery = params.get("server");
  if (fromQuery) q.set("server", fromQuery);
  const search = q.toString();
  return (
    <Navigate to={`/settings/host${search ? `?${search}` : ""}`} replace />
  );
}
