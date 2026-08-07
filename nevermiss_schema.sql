-- =================================================================================
-- NeverMiss AI Admin Dashboard - PostgreSQL Multi-Tenant Schema (with RLS)
-- =================================================================================

-- 1. Enable pgvector for embeddings and uuid-ossp for UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 2. Tenants Table (Core Multi-Tenancy)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Enable RLS for all tables going forward
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON tenants
    USING (id = current_setting('app.current_tenant_id')::UUID);

-- 3. Customers (CRM Contacts)
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone_number VARCHAR(50),
    name VARCHAR(255),
    email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
CREATE POLICY customer_tenant_policy ON customers USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 4. Voice Agents (ElevenLabs Config)
CREATE TABLE voice_agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_name VARCHAR(255) NOT NULL,
    elevenlabs_agent_id VARCHAR(255) NOT NULL,
    twilio_phone_number VARCHAR(50),
    greeting_script TEXT,
    system_prompt TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE voice_agents ENABLE ROW LEVEL SECURITY;
CREATE POLICY agent_tenant_policy ON voice_agents USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 5. Integration Configs (Calendar/CRM)
CREATE TABLE integrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    integration_type VARCHAR(100) NOT NULL, -- e.g., 'google_calendar', 'servicetitan'
    credentials_secret_id VARCHAR(255), -- Reference to Azure Key Vault / AWS Secrets
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;
CREATE POLICY integration_tenant_policy ON integrations USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 6. Calls (Event Telemetry)
CREATE TABLE calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    voice_agent_id UUID NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    call_start_time TIMESTAMP WITH TIME ZONE,
    call_end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    status VARCHAR(50), -- e.g., 'completed', 'failed', 'voicemail'
    outcome_mix VARCHAR(100), -- 'booked', 'callback', 'unqualified', 'spam'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
CREATE POLICY call_tenant_policy ON calls USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 7. Transcripts
CREATE TABLE transcripts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    raw_text TEXT NOT NULL,
    embedding vector(1536), -- for semantic search over transcripts
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE transcripts ENABLE ROW LEVEL SECURITY;
CREATE POLICY transcript_tenant_policy ON transcripts USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 8. Recordings
CREATE TABLE recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    storage_url VARCHAR(1024) NOT NULL, -- Azure Blob Storage URL
    duration_seconds INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE recordings ENABLE ROW LEVEL SECURITY;
CREATE POLICY recording_tenant_policy ON recordings USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 9. Appointments
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    call_id UUID REFERENCES calls(id) ON DELETE SET NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
    scheduled_time TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) DEFAULT 'scheduled',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
CREATE POLICY appointment_tenant_policy ON appointments USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- =================================================================================
-- EVALUATIONS & RUBRICS (Phase 2 core)
-- =================================================================================

-- 10. Eval Rubrics
CREATE TABLE eval_rubrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE eval_rubrics ENABLE ROW LEVEL SECURITY;
CREATE POLICY rubric_tenant_policy ON eval_rubrics USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 11. Eval Criteria
CREATE TABLE eval_criteria (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    rubric_id UUID NOT NULL REFERENCES eval_rubrics(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    prompt_instruction TEXT NOT NULL, -- e.g. "Did the agent collect the user's email?"
    weight_percentage INTEGER DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE eval_criteria ENABLE ROW LEVEL SECURITY;
CREATE POLICY eval_criteria_tenant_policy ON eval_criteria USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 12. Eval Results (Post-call AI evaluation output)
CREATE TABLE eval_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    criterion_id UUID NOT NULL REFERENCES eval_criteria(id) ON DELETE CASCADE,
    score INTEGER NOT NULL, -- 0 to 100
    ai_reasoning TEXT NOT NULL, -- Explanation of the score
    is_flagged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE eval_results ENABLE ROW LEVEL SECURITY;
CREATE POLICY eval_result_tenant_policy ON eval_results USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 13. Prompt Revisions (HITL Review Queue)
CREATE TABLE prompt_revisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    voice_agent_id UUID NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,
    eval_result_id UUID REFERENCES eval_results(id) ON DELETE CASCADE,
    original_prompt TEXT NOT NULL,
    suggested_revision TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    reviewed_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);
ALTER TABLE prompt_revisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY prompt_revision_tenant_policy ON prompt_revisions USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
