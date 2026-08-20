import re

with open("dashboard/src/app/board/page.tsx", "r") as f:
    content = f.read()

# Add import at the top
if 'import { KenbunMetadata, parseCardMetadata, injectCardMetadata }' not in content:
    content = content.replace('import { createPlankaClient } from', 'import { KenbunMetadata, parseCardMetadata, injectCardMetadata } from "../../lib/metadata";\nimport { createPlankaClient } from')

# Remove the interface and functions
content = re.sub(r'interface KenbunMetadata \{[\s\S]*?\}', '', content)
content = re.sub(r'const KenbunMetadataSchema = z\.object\(\{[\s\S]*?\}\)\.strict\(\);', '', content)
content = re.sub(r'const DescriptionInputSchema = z\.string\(\)\.max\(50000\)\.catch\(""\);', '', content)
content = re.sub(r'function sanitizeText\(input: string\): string \{[\s\S]*?\}\n', '', content)
content = re.sub(r'// Helpers for metadata parsing\nfunction parseCardMetadata[\s\S]*?return \{ cleanDescription: sanitizeText\(inputStr\), metadata: \{\} \};\n\}', '', content)
content = re.sub(r'function injectCardMetadata\(description: string, metadata: KenbunMetadata\): string \{[\s\S]*?\}', '', content)

with open("dashboard/src/app/board/page.tsx", "w") as f:
    f.write(content)
