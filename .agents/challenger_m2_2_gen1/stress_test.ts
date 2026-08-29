import { LeadSchema, LeadMetadataSchema, BudgetSchema, CommercialSchema, SafeStringSchema, RequestDateSchema } from "../../dashboard/src/lib/validation";

function runTests() {
  console.log("🧪 Starting Zod Metadata Validation Stress Tests...\n");
  let passCount = 0;
  let failCount = 0;

  function assert(condition: boolean, message: string) {
    if (condition) {
      console.log(`✅ PASS: ${message}`);
      passCount++;
    } else {
      console.error(`❌ FAIL: ${message}`);
      failCount++;
    }
  }

  // Helper to check if property is an own property
  function hasOwn(obj: any, prop: string): boolean {
    return Object.prototype.hasOwnProperty.call(obj, prop);
  }

  // 1. PROTOTYPE POLLUTION TESTS
  try {
    const maliciousPayload = {
      id: "4ba4e6b2-a42e-4b68-b789-f5383569c7ad",
      name: "Exploit Lead",
      __proto__: { polluted: true },
      metadata: {
        budget: "$10,000",
        request_date: "2026-07-07",
        commercial: true,
        __proto__: { pollutedMetadata: true },
        constructor: { prototype: { pollutedConstructor: true } }
      }
    };

    const parsed = LeadSchema.parse(maliciousPayload);

    // Verify properties are stripped and not in own properties of output
    assert(!hasOwn(parsed, "__proto__"), "Root __proto__ should not exist as an own property in parsed lead");
    assert(!hasOwn(parsed, "polluted"), "Root polluted property should not exist as an own property in parsed lead");
    assert(!hasOwn(parsed.metadata, "__proto__"), "Metadata __proto__ should not exist as an own property in parsed metadata");
    assert(!hasOwn(parsed.metadata, "pollutedMetadata"), "Metadata pollutedMetadata should not exist as an own property");
    assert(!hasOwn(parsed.metadata, "constructor"), "Metadata constructor should not exist as an own property");

    // Verify global prototype is not polluted
    const obj: any = {};
    assert(obj.polluted === undefined, "Global Object.prototype should not be polluted by root __proto__");
    assert(obj.pollutedMetadata === undefined, "Global Object.prototype should not be polluted by metadata __proto__");
    assert(obj.pollutedConstructor === undefined, "Global Object.prototype should not be polluted by constructor");
  } catch (err) {
    console.error("Prototype pollution test threw unexpected error:", err);
    failCount++;
  }

  // 2. UNKNOWN / MALICIOUS KEYS STRIPPING
  try {
    const payloadWithExtraKeys = {
      id: "4ba4e6b2-a42e-4b68-b789-f5383569c7ad",
      name: "Lead with Extra Keys",
      isAdmin: true,
      role: "superuser",
      delete_all_records: true,
      metadata: {
        budget: "$5,000",
        request_date: "2026-07-07",
        commercial: false,
        isAdmin: true,
        extraMeta: "dangerous"
      }
    };

    const parsed = LeadSchema.parse(payloadWithExtraKeys);
    assert((parsed as any).isAdmin === undefined, "Root isAdmin key should be stripped");
    assert((parsed as any).role === undefined, "Root role key should be stripped");
    assert((parsed as any).delete_all_records === undefined, "Root delete_all_records key should be stripped");
    assert((parsed.metadata as any).isAdmin === undefined, "Metadata isAdmin key should be stripped");
    assert((parsed.metadata as any).extraMeta === undefined, "Metadata extraMeta key should be stripped");
  } catch (err) {
    console.error("Key stripping test threw unexpected error:", err);
    failCount++;
  }

  // 3. BUDGET COERCION TESTS
  const budgetCases = [
    { input: 10000, expected: 10000, desc: "number budget" },
    { input: "$10,000", expected: 10000, desc: "standard currency string" },
    { input: "$ 12,345.67", expected: 12345.67, desc: "currency with space and cents" },
    { input: "-$100", expected: 100, desc: "negative sign is stripped" },
    { input: "abc", expected: 0, desc: "non-numeric string yields 0" },
    { input: "", expected: 0, desc: "empty string yields 0" },
    { input: "  $150.50  ", expected: 150.50, desc: "currency with whitespace" },
  ];

  for (const tc of budgetCases) {
    try {
      const res = BudgetSchema.parse(tc.input);
      assert(res === tc.expected, `Budget coercion for [${tc.input}] (${tc.desc}) -> ${res}`);
    } catch (err) {
      console.error(`Budget coercion failed for input ${tc.input}:`, err);
      failCount++;
    }
  }

  // Budget validation error cases (must fail parsing)
  const invalidBudgets = [null, undefined, {}, []];
  for (const tc of invalidBudgets) {
    try {
      BudgetSchema.parse(tc);
      console.error(`❌ FAIL: BudgetSchema should throw for invalid type ${typeof tc}`);
      failCount++;
    } catch (err) {
      assert(true, `BudgetSchema correctly threw for invalid type ${typeof tc}`);
    }
  }

  // 4. COMMERCIAL COERCION TESTS
  const commercialCases = [
    { input: true, expected: true, desc: "boolean true" },
    { input: false, expected: false, desc: "boolean false" },
    { input: "true", expected: true, desc: "string true" },
    { input: "TRUE", expected: true, desc: "uppercase string true" },
    { input: "1", expected: true, desc: "string 1" },
    { input: 1, expected: true, desc: "number 1" },
    { input: "false", expected: false, desc: "string false" },
    { input: "0", expected: false, desc: "string 0" },
    { input: 0, expected: false, desc: "number 0" },
    { input: "random", expected: false, desc: "random string yields false" },
    { input: 999, expected: false, desc: "other numbers yield false" },
  ];

  for (const tc of commercialCases) {
    try {
      const res = CommercialSchema.parse(tc.input);
      assert(res === tc.expected, `Commercial coercion for [${tc.input}] (${tc.desc}) -> ${res}`);
    } catch (err) {
      console.error(`Commercial coercion failed for input ${tc.input}:`, err);
      failCount++;
    }
  }

  // Commercial invalid types
  const invalidCommercial = [null, undefined, {}, []];
  for (const tc of invalidCommercial) {
    try {
      CommercialSchema.parse(tc);
      console.error(`❌ FAIL: CommercialSchema should throw for invalid type ${typeof tc}`);
      failCount++;
    } catch (err) {
      assert(true, `CommercialSchema correctly threw for invalid type ${typeof tc}`);
    }
  }

  // 5. XSS ESCAPING / SAFE STRING TESTS
  const xssCases = [
    {
      input: "<script>alert('xss')</script>",
      expected: "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;&#x2F;script&gt;",
      desc: "simple script tag"
    },
    {
      input: "<img src=x onerror=alert(1)>",
      expected: "&lt;img src=x onerror=alert(1)&gt;",
      desc: "img tag with onerror"
    },
    {
      input: "javascript:alert(1)",
      expected: "javascript:alert(1)",
      desc: "javascript URI scheme (SafeStringSchema only escapes HTML tag chars)"
    },
    {
      input: "nested &lt;script&gt;",
      expected: "nested &lt;script&gt;",
      desc: "normalization prevents double-escaping"
    },
    {
      input: "nested &amp;lt;script&amp;gt;",
      expected: "nested &lt;script&gt;",
      desc: "normalization handles double-encoded entities"
    }
  ];

  for (const tc of xssCases) {
    try {
      const res = SafeStringSchema.parse(tc.input);
      assert(res === tc.expected, `SafeString escaping for [${tc.input}] (${tc.desc}) -> ${res}`);
    } catch (err) {
      console.error(`SafeString parsing failed for input ${tc.input}:`, err);
      failCount++;
    }
  }

  // 6. REQUEST DATE SCHEMA TESTS
  const validDates = ["2026-07-07", "2000-01-01", "1999-12-31"];
  for (const d of validDates) {
    try {
      const res = RequestDateSchema.parse(d);
      assert(res === d, `RequestDateSchema accepts valid date format: ${d}`);
    } catch (err) {
      console.error(`RequestDateSchema failed for valid date ${d}:`, err);
      failCount++;
    }
  }

  const invalidDates = ["2026-7-7", "07-07-2026", "2026/07/07", "invalid", "", "2026-07-07 10:00"];
  for (const d of invalidDates) {
    try {
      RequestDateSchema.parse(d);
      console.error(`❌ FAIL: RequestDateSchema should reject invalid format: ${d}`);
      failCount++;
    } catch (err) {
      assert(true, `RequestDateSchema correctly rejected invalid format: ${d}`);
    }
  }

  console.log(`\n📊 Stress Test Results: ${passCount} PASSED, ${failCount} FAILED.`);
  process.exit(failCount > 0 ? 1 : 0);
}

runTests();
