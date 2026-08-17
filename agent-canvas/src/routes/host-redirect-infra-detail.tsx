import { Navigate, useParams } from "react-router";

/** Legacy /admin/infra/:serverId → Settings → Host */
export default function HostRedirectInfraDetail() {
  const { serverId } = useParams();
  const search = serverId ? `?server=${encodeURIComponent(serverId)}` : "";
  return <Navigate to={`/settings/host${search}`} replace />;
}
