-- Supabase PostgreSQL Schema for NeverMiss AI

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table: Business (Tenants)
CREATE TABLE public.business (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    timezone TEXT DEFAULT 'UTC',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table: VoiceAgent
CREATE TABLE public.voice_agent (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES public.business(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    voice_id TEXT NOT NULL,
    script TEXT,
    hours JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table: Call
CREATE TABLE public.call (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES public.voice_agent(id) ON DELETE CASCADE,
    caller_number TEXT NOT NULL,
    transcript TEXT,
    recording_url TEXT,
    outcome TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table: Customer
CREATE TABLE public.customer (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES public.business(id) ON DELETE CASCADE,
    phone TEXT NOT NULL,
    name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(business_id, phone)
);

-- Table: Appointment
CREATE TABLE public.appointment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES public.customer(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES public.voice_agent(id) ON DELETE CASCADE,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    status TEXT DEFAULT 'scheduled',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table: CalendarIntegration
CREATE TABLE public.calendar_integration (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES public.business(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(business_id, provider)
);

-- Set up Row Level Security (RLS)

-- 1. Enable RLS on all tables
ALTER TABLE public.business ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voice_agent ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.call ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customer ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appointment ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.calendar_integration ENABLE ROW LEVEL SECURITY;

-- 2. Create basic policies for authenticated users
-- Assuming authenticated users have a linked business_id in auth.users or app_metadata
-- For the sake of this migration, we'll setup generic policies using a hypothetical auth function
-- `auth.jwt() -> 'business_id'`

CREATE POLICY "Users can access their own business"
ON public.business FOR ALL
USING (id = (auth.jwt() ->> 'business_id')::UUID);

CREATE POLICY "Users can access their own agents"
ON public.voice_agent FOR ALL
USING (business_id = (auth.jwt() ->> 'business_id')::UUID);

CREATE POLICY "Users can access calls for their agents"
ON public.call FOR ALL
USING (agent_id IN (SELECT id FROM public.voice_agent WHERE business_id = (auth.jwt() ->> 'business_id')::UUID));

CREATE POLICY "Users can access their own customers"
ON public.customer FOR ALL
USING (business_id = (auth.jwt() ->> 'business_id')::UUID);

CREATE POLICY "Users can access appointments for their customers"
ON public.appointment FOR ALL
USING (customer_id IN (SELECT id FROM public.customer WHERE business_id = (auth.jwt() ->> 'business_id')::UUID));

CREATE POLICY "Users can access their own calendar integrations"
ON public.calendar_integration FOR ALL
USING (business_id = (auth.jwt() ->> 'business_id')::UUID);
