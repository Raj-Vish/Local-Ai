// Stand-in content for a backend that does not exist yet. Everything the
// assistant "knows" lives here; replacing these with real calls is the whole
// job of wiring this UI to a server.

export const MOCK_HISTORY_DATA = {
  "Q3 Policy Query": [
    { role: "user", content: "Can you summarize the Q3 remote work policy?" },
    { role: "assistant", content: "Certainly. Here is the structured summary of the updated Q3 Policy:\n\n• Core Hours: Employees must be online and available between 10 AM and 3 PM.\n• Remote Days: Up to 3 days of remote work per week are permitted.\n• Hardware Support: Stipends for home office setups have been increased by 15%.\n\nPlease let me know if you need specific details extracted from the HR handbook." }
  ],
  "Attendance System Specs": [
    { role: "user", content: "What are the specs for the new attendance system API?" },
    { role: "assistant", content: "The new Attendance API (v2.4) specifications are strictly defined as follows:\n\n• Authentication: OAuth 2.0 is required for all endpoint access.\n• Rate Limits: 100 requests per minute per user token.\n• Payload structure: JSON format is strictly enforced for the POST /attendance/log route.\n\nThe full documentation has been indexed in your department's access vault." }
  ],
  "IT Password Reset Steps": [
    { role: "user", content: "How do I reset my active directory password?" },
    { role: "assistant", content: "To reset your Active Directory password securely, please follow these steps:\n\n• Navigate to the internal myaccess.company.local portal.\n• Authenticate using your secondary 2FA device (Duo or Authenticator App).\n• Select 'Reset Password' and ensure your new password meets the 14-character minimum requirement.\n\nIf you are locked out completely, you will need to call the IT Helpdesk directly." }
  ]
};

export const INITIAL_CHAT_HISTORY = Object.keys(MOCK_HISTORY_DATA);

export const SUGGESTED_PROMPTS = [
  "Summarize the Q3 remote work policy",
  "What are the attendance API rate limits?",
  "How do I reset my Active Directory password?",
  "Which expense categories need pre-approval?"
];

export const buildMockReply = (userText) =>
  `Based on internal records, here is the structured breakdown regarding "${userText}":\n\n• Data Security: All queried chunks are processed locally.\n• Relevance: Information matched against your department role.\n• Next Steps: Review the output and verify against departmental SOPs.\n\nLet me know if you need to refine this query.`;

export const buildRecoveredThread = (topic) => [
  { role: "user", content: topic },
  { role: "assistant", content: `Here is the recovered session data regarding:\n\n"${topic}"\n\nAll contextual memory has been loaded.` }
];
