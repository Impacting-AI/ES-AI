CREATE TABLE IF NOT EXISTS users(id text PRIMARY KEY, login text UNIQUE NOT NULL, password text NOT NULL);
ALTER TABLE users DROP COLUMN IF EXISTS otp_encrypted, DROP COLUMN IF EXISTS last_step;
CREATE TABLE IF NOT EXISTS sessions(token text PRIMARY KEY, uid text NOT NULL REFERENCES users, expires bigint NOT NULL);
CREATE TABLE IF NOT EXISTS attempts(bucket text PRIMARY KEY, began bigint NOT NULL, count integer NOT NULL);
CREATE TABLE IF NOT EXISTS projects(id text PRIMARY KEY, name text NOT NULL, client text NOT NULL, created timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS members(pid text REFERENCES projects, uid text REFERENCES users, PRIMARY KEY(pid,uid));
CREATE TABLE IF NOT EXISTS sources(id text PRIMARY KEY, pid text NOT NULL REFERENCES projects, title text NOT NULL, category text NOT NULL, origin text NOT NULL, description text NOT NULL DEFAULT '', state text NOT NULL DEFAULT 'draft', original text, content bytea, family text NOT NULL, version integer NOT NULL, created timestamptz DEFAULT now(), UNIQUE(pid,family,version), UNIQUE(pid,id));
CREATE UNIQUE INDEX IF NOT EXISTS one_current ON sources(pid,family) WHERE state='approved';
CREATE TABLE IF NOT EXISTS passages(id text PRIMARY KEY, pid text NOT NULL, sid text NOT NULL, position integer NOT NULL, body text NOT NULL, FOREIGN KEY(pid,sid) REFERENCES sources(pid,id));
CREATE INDEX IF NOT EXISTS passages_project ON passages(pid);
CREATE TABLE IF NOT EXISTS audit(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, pid text REFERENCES projects, uid text REFERENCES users, action text NOT NULL, subject text NOT NULL, created timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS messages(id text PRIMARY KEY, pid text NOT NULL REFERENCES projects, role text NOT NULL, body text NOT NULL, refs text NOT NULL DEFAULT '[]', created timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS config(id integer PRIMARY KEY, provider text NOT NULL, model text NOT NULL);
CREATE TABLE IF NOT EXISTS plans(id text PRIMARY KEY, pid text NOT NULL REFERENCES projects, content text NOT NULL, state text NOT NULL DEFAULT 'draft', created timestamptz DEFAULT now());
ALTER TABLE plans ADD COLUMN IF NOT EXISTS scope_ids text NOT NULL DEFAULT '[]';
CREATE TABLE IF NOT EXISTS feedback(id text PRIMARY KEY, pid text NOT NULL REFERENCES projects, uid text NOT NULL REFERENCES users, target text NOT NULL, category text NOT NULL, body text NOT NULL, created timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS agent_settings(agent_id text PRIMARY KEY,revision integer NOT NULL,policy jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS agent_versions(agent_id text NOT NULL,revision integer NOT NULL,policy jsonb NOT NULL,actor text REFERENCES users,created timestamptz DEFAULT now(),PRIMARY KEY(agent_id,revision));
CREATE TABLE IF NOT EXISTS agent_credentials(agent_id text NOT NULL, service text NOT NULL, encrypted text, updated timestamptz DEFAULT now(),PRIMARY KEY(agent_id,service));
CREATE TABLE IF NOT EXISTS agent_runs(id text PRIMARY KEY, pid text REFERENCES projects, uid text REFERENCES users, action text NOT NULL,status text NOT NULL, detail text NOT NULL DEFAULT '',revision integer NOT NULL DEFAULT 0,created timestamptz DEFAULT now(),finished timestamptz);
CREATE INDEX IF NOT EXISTS agent_runs_by_project ON agent_runs(pid,created);
CREATE TABLE IF NOT EXISTS agent_digests(pid text REFERENCES projects,local_day date NOT NULL,body text NOT NULL,created timestamptz DEFAULT now(),PRIMARY KEY(pid,local_day));
CREATE TABLE IF NOT EXISTS agent_actions(id text PRIMARY KEY,pid text REFERENCES projects NOT NULL,service text NOT NULL,payload jsonb NOT NULL,status text NOT NULL DEFAULT 'draft',revision integer NOT NULL,target text NOT NULL,created_by text REFERENCES users,approved_by text REFERENCES users,remote_id text,created timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS project_staff(pid text NOT NULL REFERENCES projects, id text PRIMARY KEY, name text NOT NULL, role text NOT NULL,skills text NOT NULL,jira_id text NOT NULL,slack_id text NOT NULL,hours numeric NOT NULL,UNIQUE(pid,name));
CREATE TABLE IF NOT EXISTS project_links(pid text NOT NULL REFERENCES projects, service text NOT NULL,workspace text NOT NULL,destination text NOT NULL,PRIMARY KEY(pid,service),UNIQUE(service,workspace,destination));
CREATE TABLE IF NOT EXISTS delivery_events(pid text NOT NULL REFERENCES projects,service text NOT NULL,remote_id text NOT NULL,record jsonb NOT NULL,happened timestamptz NOT NULL,synced timestamptz DEFAULT now(),PRIMARY KEY(pid,service,remote_id));
CREATE TABLE IF NOT EXISTS agent_usage(id text PRIMARY KEY,pid text NOT NULL REFERENCES projects,provider text NOT NULL,model text NOT NULL,input_tokens integer,output_tokens integer,estimated_usd numeric NOT NULL,settled boolean NOT NULL DEFAULT false,created timestamptz DEFAULT now());

CREATE UNIQUE INDEX IF NOT EXISTS action_content_revision ON agent_actions(pid,service,revision,md5(payload::text));
ALTER TABLE agent_actions ADD COLUMN IF NOT EXISTS plan_id text REFERENCES plans;
CREATE UNIQUE INDEX IF NOT EXISTS dispatched_once ON agent_actions(pid,service,target,md5(payload::text)) WHERE status IN ('dispatching','confirmed','needs reconciliation');
ALTER TABLE users ADD COLUMN IF NOT EXISTS platform_role text NOT NULL DEFAULT 'Super Admin';
ALTER TABLE users ADD COLUMN IF NOT EXISTS agent_access boolean NOT NULL DEFAULT true;
CREATE TABLE IF NOT EXISTS report_drafts(id text PRIMARY KEY,pid text REFERENCES projects,uid text REFERENCES users,audience text NOT NULL,period_start date NOT NULL,period_end date NOT NULL,body text NOT NULL,revision integer NOT NULL DEFAULT 1,created timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS chat_imports(pid text REFERENCES projects,digest text NOT NULL,sid text REFERENCES sources,PRIMARY KEY(pid,digest));
CREATE TABLE IF NOT EXISTS connection_checks (
 agent_id text NOT NULL, service text NOT NULL, fingerprint text NOT NULL,
 ok boolean NOT NULL, detail text NOT NULL, checked_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(agent_id,service,fingerprint)
);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS archived boolean NOT NULL DEFAULT false;
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS board_id text;
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS poll_after timestamptz;
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS sync_status text;
ALTER TABLE agent_actions ADD COLUMN IF NOT EXISTS work_key text;
ALTER TABLE agent_actions ADD COLUMN IF NOT EXISTS parent_key text;
ALTER TABLE agent_actions ADD COLUMN IF NOT EXISTS prerequisites jsonb NOT NULL DEFAULT '[]';
CREATE UNIQUE INDEX IF NOT EXISTS plan_work_revision ON agent_actions(plan_id,revision,work_key) WHERE work_key IS NOT NULL;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS profile jsonb NOT NULL DEFAULT '{}';
CREATE TABLE IF NOT EXISTS improvement_proposals(id text PRIMARY KEY,pid text NOT NULL REFERENCES projects,uid text NOT NULL REFERENCES users,revision integer NOT NULL,policy_text text NOT NULL,category text NOT NULL,evidence jsonb NOT NULL,status text NOT NULL DEFAULT 'draft',created timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS report_rules(pid text PRIMARY KEY REFERENCES projects,uid text NOT NULL REFERENCES users,config jsonb NOT NULL,updated timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS report_occurrences(pid text REFERENCES projects,day date,report_id text REFERENCES report_drafts,PRIMARY KEY(pid,day));

ALTER TABLE improvement_proposals ADD COLUMN IF NOT EXISTS evaluation text;
ALTER TABLE improvement_proposals ADD COLUMN IF NOT EXISTS reviewer text REFERENCES users;

ALTER TABLE users ALTER COLUMN platform_role SET DEFAULT 'Read-Only';

ALTER TABLE improvement_proposals ADD COLUMN IF NOT EXISTS prior_guidance text;

ALTER TABLE sources ADD COLUMN IF NOT EXISTS processing text;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS processing_error text NOT NULL DEFAULT '';
ALTER TABLE passages ADD COLUMN IF NOT EXISTS location text NOT NULL DEFAULT '';
UPDATE sources s SET processing=CASE WHEN EXISTS(SELECT 1 FROM passages p WHERE p.pid=s.pid AND p.sid=s.id) THEN 'Ready' ELSE 'Uploaded' END WHERE processing IS NULL;
ALTER TABLE sources ALTER COLUMN processing SET DEFAULT 'Ready';
CREATE TABLE IF NOT EXISTS chat_threads(id text PRIMARY KEY,pid text NOT NULL REFERENCES projects,owner_id text REFERENCES users,title text NOT NULL,archived boolean NOT NULL DEFAULT false,summary text NOT NULL DEFAULT '',revision integer NOT NULL DEFAULT 0,updated timestamptz NOT NULL DEFAULT now(),UNIQUE(pid,id));
ALTER TABLE messages ADD COLUMN IF NOT EXISTS thread_id text;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS citations jsonb NOT NULL DEFAULT '[]';
ALTER TABLE messages ADD COLUMN IF NOT EXISTS files jsonb NOT NULL DEFAULT '[]';
INSERT INTO chat_threads(id,pid,title) SELECT DISTINCT 'legacy-'||pid,pid,'Earlier project chat' FROM messages WHERE thread_id IS NULL ON CONFLICT DO NOTHING;
UPDATE messages SET thread_id='legacy-'||pid WHERE thread_id IS NULL;
CREATE INDEX IF NOT EXISTS thread_messages ON messages(pid,thread_id,created);
CREATE TABLE IF NOT EXISTS chat_files(id text PRIMARY KEY,pid text NOT NULL,thread_id text NOT NULL,name text NOT NULL,parts jsonb NOT NULL,created timestamptz DEFAULT now(),FOREIGN KEY(pid,thread_id) REFERENCES chat_threads(pid,id));

ALTER TABLE chat_files ADD COLUMN IF NOT EXISTS original bytea;


CREATE INDEX IF NOT EXISTS message_terms ON messages USING gin(to_tsvector('simple',body));

ALTER TABLE chat_threads ADD COLUMN IF NOT EXISTS created timestamptz;
UPDATE chat_threads t SET created=coalesce((SELECT min(created) FROM messages WHERE thread_id=t.id AND pid=t.pid),t.updated) WHERE created IS NULL;
ALTER TABLE chat_threads ALTER COLUMN created SET DEFAULT now();
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS thread_id text REFERENCES chat_threads(id);
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS message_ids jsonb NOT NULL DEFAULT '[]';
ALTER TABLE improvement_proposals ADD COLUMN IF NOT EXISTS analysis text NOT NULL DEFAULT '';
ALTER TABLE improvement_proposals ADD COLUMN IF NOT EXISTS applied jsonb NOT NULL DEFAULT '{}';
ALTER TABLE improvement_proposals ADD COLUMN IF NOT EXISTS edit_version integer NOT NULL DEFAULT 1;
ALTER TABLE improvement_proposals ADD COLUMN IF NOT EXISTS updated timestamptz NOT NULL DEFAULT now();
CREATE TABLE IF NOT EXISTS feedback_versions(proposal_id text REFERENCES improvement_proposals(id),version integer,body text NOT NULL,analysis text NOT NULL,status text NOT NULL,applied jsonb NOT NULL,actor text REFERENCES users,recorded timestamptz DEFAULT now(),PRIMARY KEY(proposal_id,version));

ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS diagnostics jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE chat_threads ADD COLUMN IF NOT EXISTS generation_id text;
ALTER TABLE chat_threads ADD COLUMN IF NOT EXISTS generation_until timestamptz;

ALTER TABLE project_links ADD COLUMN IF NOT EXISTS mapping_id uuid NOT NULL DEFAULT gen_random_uuid();
CREATE UNIQUE INDEX IF NOT EXISTS project_mapping_identity ON project_links(mapping_id);
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS external_id text;
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS resource_name text;
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS resource_url text;
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS verified_at timestamptz;
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS last_sync timestamptz;
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS last_full timestamptz;
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS scan_started timestamptz;
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS scan_cursor text NOT NULL DEFAULT '';
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS scan_full boolean NOT NULL DEFAULT true;
ALTER TABLE project_links ADD COLUMN IF NOT EXISTS queued boolean NOT NULL DEFAULT true;
ALTER TABLE delivery_events ADD COLUMN IF NOT EXISTS mapping_id uuid NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000';
-- Historical rows lacking provenance remain archived. The worker fetches fresh rows.
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='delivery_events'::regclass
     AND contype='p' AND pg_get_constraintdef(oid) LIKE '%mapping_id%') THEN
   ALTER TABLE delivery_events DROP CONSTRAINT delivery_events_pkey;
   ALTER TABLE delivery_events ADD PRIMARY KEY(pid,service,mapping_id,remote_id);
 END IF;
END $$;
CREATE OR REPLACE VIEW mapped_delivery_events AS
 SELECT e.* FROM delivery_events e JOIN project_links l USING(pid,service,mapping_id)
 JOIN agent_settings a ON a.agent_id='pm-ai-es'
 WHERE l.verified_at IS NOT NULL AND
 ((l.service='Jira' AND l.workspace=a.policy->>'jira_site' AND coalesce((a.policy->>'sync_jira')::boolean,true))
 OR (l.service='Slack' AND l.workspace=a.policy->>'slack_team' AND coalesce((a.policy->>'sync_slack')::boolean,true)));

ALTER TABLE projects ADD COLUMN IF NOT EXISTS connections_changed timestamptz;
CREATE OR REPLACE FUNCTION mark_project_connection_change() RETURNS trigger AS $$
BEGIN
 IF TG_OP='DELETE' THEN UPDATE projects SET connections_changed=clock_timestamp() WHERE id=OLD.pid;
 ELSE UPDATE projects SET connections_changed=clock_timestamp() WHERE id=NEW.pid; END IF;
 UPDATE chat_threads SET summary='',generation_id=NULL,generation_until=NULL WHERE pid=CASE WHEN TG_OP='DELETE' THEN OLD.pid ELSE NEW.pid END;
 RETURN NULL;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS mapping_changed ON project_links;
CREATE TRIGGER mapping_changed AFTER INSERT OR DELETE OR UPDATE OF mapping_id ON project_links FOR EACH ROW EXECUTE FUNCTION mark_project_connection_change();

CREATE OR REPLACE FUNCTION invalidate_provider_links() RETURNS trigger AS $$
BEGIN
 UPDATE project_links SET mapping_id=gen_random_uuid(),last_sync=NULL,verified_at=NULL,queued=true,poll_after=now(),scan_cursor='',scan_started=NULL,last_full=NULL,
 sync_status='Credential changed. Verify connection.' WHERE service=NEW.service;
 RETURN NULL;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS provider_key_changed ON agent_credentials;
CREATE TRIGGER provider_key_changed AFTER INSERT OR UPDATE OF encrypted ON agent_credentials FOR EACH ROW EXECUTE FUNCTION invalidate_provider_links();

CREATE OR REPLACE FUNCTION invalidate_workspace_links() RETURNS trigger AS $$
BEGIN
 UPDATE project_links SET mapping_id=gen_random_uuid(),verified_at=NULL,queued=true,poll_after=now(),scan_cursor='',scan_started=NULL,
 last_full=NULL,last_sync=NULL,sync_status='Workspace changed. Verify connection.'
 WHERE (service='Jira' AND (OLD.policy->>'jira_site',OLD.policy->>'jira_email') IS DISTINCT FROM (NEW.policy->>'jira_site',NEW.policy->>'jira_email'))
 OR (service='Slack' AND OLD.policy->>'slack_team' IS DISTINCT FROM NEW.policy->>'slack_team');
 RETURN NULL;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS provider_workspace_changed ON agent_settings;
CREATE TRIGGER provider_workspace_changed AFTER UPDATE OF policy ON agent_settings FOR EACH ROW EXECUTE FUNCTION invalidate_workspace_links();
