import json
import random
from pathlib import Path

# --- TEMPLATES ---
templates = {
    "UI_FIX_PATH": [
        "The {element} is not {issue} on {device}. Fix the layout.",
        "The {element} in the {component} is {issue}. Please resolve.",
        "Regression: {element} stopped {issue} after the last CSS update.",
        "Broken {element} on {device}. It needs to be {fix_action}.",
        "The {element} is overlapping with the {other_element}. Fix the z-index/flex."
    ],
    "SECURITY_HARDENING_PATH": [
        "Audit the {module} for {vuln} vulnerabilities.",
        "Implement {sec_feature} to prevent {attack} attacks.",
        "Check if the {auth_method} can be bypassed by {exploit}.",
        "Scan the {module} code for potential {vuln} leaks.",
        "Hardening: Secure the {module} endpoint against {attack}."
    ],
    "ARCHITECT_RESEARCH_PATH": [
        "Research how to {action} our {system} for {scale} users.",
        "Design a {system} strategy for {scale} scalability.",
        "Compare {tech_a} vs {tech_b} for our {system} infrastructure.",
        "Refactor the {module} to use a more {strategy} architecture.",
        "Migrate the {system} from {old_tech} to {new_tech}."
    ],
    "UI_COMPONENT_BUILD": [
        "Create a {style} {element} component using {tech}.",
        "Build a {element} with {style} aesthetic and {animation} animations.",
        "Develop a {style} landing page section for {topic}.",
        "Implement a {element} that uses {tech} for its styling.",
        "Design a new {element} for the {component} library."
    ],
    "STANDARD_BUG_FIX": [
        "The {module} is {issue}. Please fix the logic error.",
        "Resolve the {issue} in the {module} function.",
        "Fix the {issue} where the {module} crashes on {action_event}.",
        "The {module} is not {issue} as expected. Check the return values.",
        "Correct the {issue} in the {module} logic."
    ]
}

# --- VOCABULARY ---
vocab = {
    "element": ["button", "modal", "navbar", "footer", "grid", "flexbox", "input", "dropdown", "sidebar", "card", "hero section", "bento grid", "canvas", "shader", "webhook", "cron job"],
    "issue": ["centering", "visible", "broken", "crashing", "lagging", "overlapping", "missing", "unresponsive", "failing", "race condition", "hydration error", "flickering", "memory leak", "infinite loop"],
    "device": ["mobile", "tablet", "desktop", "safari", "chrome", "iOS", "Android", "Firefox", "Edge"],
    "module": ["auth", "database", "api", "login", "payment", "user profile", "ingestion", "webhook", "jwt", "session", "middleware", "server action", "bucket", "vector db"],
    "vuln": ["sql injection", "xss", "data leak", "cors", "csrf", "insecure", "unauthorized access", "rce", "path traversal"],
    "sec_feature": ["rate-limiting", "sanitization", "encryption", "jwt rotation", "mfa", "rbac", "rls policies"],
    "attack": ["brute-force", "ddos", "spoofing", "injection", "hijacking", "man-in-the-middle", "replay attack"],
    "action": ["scale", "optimize", "refactor", "migrate", "transition", "benchmark", "containerize", "orchestrate"],
    "system": ["database", "frontend", "backend", "cache", "infrastructure", "deployment", "pipeline", "load balancer"],
    "scale": ["1M", "high-traffic", "enterprise", "global", "multi-region", "billion-scale"],
    "tech_a": ["Next.js", "React", "SvelteKit", "FastAPI", "Go", "Rust", "Node.js"],
    "tech_b": ["Remix", "Vue", "SolidJS", "Flask", "Django", "Spring Boot", "Laravel"],
    "style": ["glassmorphic", "brutalist", "minimalist", "modern", "premium", "sleek", "neuromorphic", "flat design"],
    "animation": ["gsap", "framer-motion", "transition", "staggered", "scroll-triggered", "lottie"],
    "tech": ["Tailwind CSS", "Vanilla CSS", "Styled Components", "Sass", "PostCSS", "Three.js"],
    "topic": ["portfolio", "dashboard", "ecommerce", "landing page", "saas app", "crypto wallet", "ai agent"],
    "action_event": ["click", "hover", "scroll", "load", "submit", "drag", "resize", "input"],
    "other_element": ["header", "image", "text block", "video background", "three.js scene", "webgl canvas"],
    "auth_method": ["JWT", "OAuth", "Session", "API Key", "Magic Link", "WebAuthn"],
    "exploit": ["spoofing", "replay attack", "injection", "padding oracle", "brute force"],
    "old_tech": ["Heroku", "AWS", "PHP", "Express", "jQuery", "REST"],
    "new_tech": ["Supabase", "Vercel", "Go", "Next.js", "GraphQL", "TRPC"],
    "strategy": ["scalable", "event-driven", "microservice", "serverless", "edge-computing", "isomorphic"],
    "noise": ["um", "actually", "please", "can you", "i need to", "just", "basically", "so like", "hey", "help me with", "could you", "i am looking to"]
}

def generate_cases(count=5000):
    cases = []
    categories = list(templates.keys())
    
    for i in range(count):
        cat = random.choice(categories)
        template = random.choice(templates[cat])
        
        # Fill template
        task = template
        for key, choices in vocab.items():
            if f"{{{key}}}" in task:
                task = task.replace(f"{{{key}}}", random.choice(choices))
        
        # Add random noise
        if random.random() > 0.5:
            prefix = random.choice(vocab["noise"])
            task = f"{prefix} {task}"
            
        # Add random punctuation
        if random.random() > 0.3:
            task += random.choice(["...", "!!!", "??", ".", "!!"])
            
        # Randomized casing
        if random.random() > 0.8:
            task = task.upper()
        elif random.random() > 0.8:
            task = task.lower()
        
        cases.append({
            "name": f"Generated {cat} {i}",
            "task": task,
            "expected_path": cat
        })
    return cases

if __name__ == "__main__":
    new_cases = generate_cases(10000)
    with open("brain_health/generated_cases.json", "w") as f:
        json.dump(new_cases, f, indent=4)
    print(f"Generated 10,000 cases in brain_health/generated_cases.json")
