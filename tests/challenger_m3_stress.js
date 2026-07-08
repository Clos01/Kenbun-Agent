import assert from "assert";
import { MetadataTransformer } from "../dashboard/src/lib/metadataTransformer";
import { 
  CurrencyCard, 
  DateCard, 
  BooleanCard, 
  ListCard, 
  StringCard 
} from "../dashboard/src/components/MetadataRegistry";

// Mock React for basic evaluation check (since framer-motion components return JSX elements)
global.React = {
  createElement: (type, props, ...children) => ({ type, props, children }),
  Component: class {}
};

console.log("=== STARTING CHALLENGER M3 CORNER CASE & STRESS TESTS ===");

// ----------------------------------------------------
// 1. Boundary & Corner cases for MetadataTransformer
// ----------------------------------------------------
console.log("\n1. Testing MetadataTransformer with empty, null, and malformed inputs...");

// Test null/undefined rawMetadata
assert.deepStrictEqual(MetadataTransformer.transform(null), []);
assert.deepStrictEqual(MetadataTransformer.transform(undefined), []);
assert.deepStrictEqual(MetadataTransformer.transform({}), []);

// Test rawMetadata with null/undefined values (should be stripped)
const strippedInput = {
  budget: null,
  request_date: undefined,
  location: "Boston",
  commercial: null
};
const strippedOutput = MetadataTransformer.transform(strippedInput);
assert.strictEqual(strippedOutput.length, 1);
assert.strictEqual(strippedOutput[0].key, "location");
assert.strictEqual(strippedOutput[0].value, "Boston");

// ----------------------------------------------------
// 2. Type Inference and Label Beautification
// ----------------------------------------------------
console.log("\n2. Testing type inference and beautifyKey for unregistered keys...");

const unregisteredInput = {
  permit_num: "PERMIT-100",           // registered field
  estimated_cost: 25000,              // unregistered, should infer currency
  dateOfSubmission: "2026-07-07",     // unregistered, should infer date
  is_approved: true,                  // unregistered, should infer boolean
  approver_list: ["Alice", "Bob"],    // unregistered, should infer list
  raw_description: "Deep foundation", // unregistered, should infer string
};

const inferredOutput = MetadataTransformer.transform(unregisteredInput);

// Check label beautification & type inference
const estimatedCost = inferredOutput.find(f => f.key === "estimated_cost");
assert.ok(estimatedCost);
assert.strictEqual(estimatedCost.label, "Estimated Cost");
assert.strictEqual(estimatedCost.type, "currency");

const dateOfSubmission = inferredOutput.find(f => f.key === "dateOfSubmission");
assert.ok(dateOfSubmission);
assert.strictEqual(dateOfSubmission.label, "Date Of Submission");
assert.strictEqual(dateOfSubmission.type, "date");

const isApproved = inferredOutput.find(f => f.key === "is_approved");
assert.ok(isApproved);
assert.strictEqual(isApproved.label, "Is Approved");
assert.strictEqual(isApproved.type, "boolean");

const approverList = inferredOutput.find(f => f.key === "approver_list");
assert.ok(approverList);
assert.strictEqual(approverList.label, "Approver List");
assert.strictEqual(approverList.type, "list");

const rawDescription = inferredOutput.find(f => f.key === "raw_description");
assert.ok(rawDescription);
assert.strictEqual(rawDescription.label, "Raw Description");
assert.strictEqual(rawDescription.type, "string");

// Check visual sorting
// Registered fields: budget (10), request_date (20), commercial (30), location (40), collections (50), recurring (60), permit_num (70)
// Unregistered fields: order 999. Sorted secondarily alphabetically by key.
// Expected order: permit_num (70), then unregistered sorted alphabetically (approver_list, dateOfSubmission, estimated_cost, is_approved, raw_description)
const keysInOrder = inferredOutput.map(f => f.key);
console.log("Keys in sorted order:", keysInOrder);
assert.deepStrictEqual(keysInOrder, [
  "permit_num",
  "approver_list",
  "dateOfSubmission",
  "estimated_cost",
  "is_approved",
  "raw_description"
]);

// ----------------------------------------------------
// 3. Extreme Data Inputs & Layout Overflow Testing
// ----------------------------------------------------
console.log("\n3. Testing transformer and components with extreme inputs...");

const extremeInput = {
  // Extremely long key name
  ["very_long_unregistered_key_name_" + "A".repeat(500)]: "Some value",
  
  // Extremely long string value
  long_string: "B".repeat(20000),
  
  // Deeply nested object property
  nested_property: {
    level1: {
      level2: {
        level3: "deep value"
      }
    }
  },
  
  // Empty array list
  empty_list: [],
  
  // Extremely long list (large bento element count)
  large_list: Array.from({ length: 1000 }, (_, i) => `item_${i}`),
  
  // Extremely long elements in list
  long_element_list: ["C".repeat(1000), "D".repeat(1000)],
  
  // Corrupted type values
  budget: "not a number", // corrupted currency
  request_date: 1234567,   // corrupted date
  commercial: [true],     // corrupted boolean
};

const extremeOutput = MetadataTransformer.transform(extremeInput);

// Verify transformer returns strings or handles them gracefully without throwing
assert.strictEqual(extremeOutput.length, 9);

const longKeyField = extremeOutput.find(f => f.key.startsWith("very_long_unregistered_key_name"));
assert.ok(longKeyField);
assert.strictEqual(longKeyField.type, "string");
assert.strictEqual(longKeyField.label.length, 532); // Beautified "Very Long Unregistered Key Name AAAA..."

const nestedPropertyField = extremeOutput.find(f => f.key === "nested_property");
assert.ok(nestedPropertyField);
assert.strictEqual(nestedPropertyField.type, "string"); // Inferred as string because it is not boolean or list
assert.deepStrictEqual(nestedPropertyField.value, { level1: { level2: { level3: "deep value" } } });

const largeListField = extremeOutput.find(f => f.key === "large_list");
assert.ok(largeListField);
assert.strictEqual(largeListField.type, "list");
assert.strictEqual(largeListField.value.length, 1000);

// Verify Registry Cards do not crash when given these fields (evaluation test)
console.log("\n4. Running evaluation render tests on Component Registry Cards...");

// Test CurrencyCard with "not a number"
try {
  const budgetField = extremeOutput.find(f => f.key === "budget");
  const jsx = CurrencyCard({ field: budgetField });
  console.log("CurrencyCard rendered successfully with invalid number:", JSON.stringify(jsx.props?.children?.props?.children)); 
} catch (err) {
  console.error("❌ CurrencyCard crashed with invalid budget value:", err);
  throw err;
}

// Test DateCard with corrupted number date
try {
  const dateField = extremeOutput.find(f => f.key === "request_date");
  const jsx = DateCard({ field: dateField });
  console.log("DateCard rendered successfully with corrupted date:", JSON.stringify(jsx.props?.children?.props?.children)); 
} catch (err) {
  console.error("❌ DateCard crashed with invalid request_date:", err);
  throw err;
}

// Test BooleanCard with array value
try {
  const commercialField = extremeOutput.find(f => f.key === "commercial");
  const jsx = BooleanCard({ field: commercialField });
  console.log("BooleanCard rendered successfully with corrupted boolean:"); 
} catch (err) {
  console.error("❌ BooleanCard crashed with invalid commercial value:", err);
  throw err;
}

// Test ListCard with large list & long elements
try {
  const largeListField = extremeOutput.find(f => f.key === "large_list");
  const jsx = ListCard({ field: largeListField });
  console.log("ListCard rendered successfully with 1000 items."); 
} catch (err) {
  console.error("❌ ListCard crashed with large list:", err);
  throw err;
}

// Test StringCard with nested object value
try {
  const nestedField = extremeOutput.find(f => f.key === "nested_property");
  const jsx = StringCard({ field: nestedField });
  console.log("StringCard rendered successfully with nested object:", JSON.stringify(jsx.props?.children?.props?.children)); 
} catch (err) {
  console.error("❌ StringCard crashed with nested object value:", err);
  throw err;
}

console.log("\n🏆 ALL CHALLENGER STRESS TESTS COMPLETED SUCCESSFULLY!");
