import { currentIdentity } from '../api/client'

export function AuditAccess() {
  const identity = currentIdentity()
  return <div className="access-wrap"><section className="access-card">
    <header className="access-heading"><p className="eyebrow">Account & access</p><h1>Your reviewer account</h1><p className="muted-copy">Your verified identity and server-assigned workspace.</p></header>
    {identity && <dl className="provenance-rows"><dt>Email</dt><dd>{identity.email}</dd><dt>Reviewer</dt><dd>{identity.actor_id}</dd><dt>Workspace</dt><dd>{identity.workspace}</dd><dt>Workspace ID</dt><dd>{identity.organization_id}</dd><dt>Role</dt><dd>{identity.role}</dd><dt>Session expires</dt><dd>{new Date(identity.expires_at * 1000).toLocaleString()}</dd></dl>}
    <p className="muted-copy access-footnote">Personal workspaces are isolated from other accounts. Organization workspaces share reviews only with explicitly assigned members. Contact your administrator to change membership or role. Linking sign-in methods is not available in this app.</p>
    <a className="primary-button" href="#/draft-workspace">Enter Draft Studio</a>
  </section></div>
}
