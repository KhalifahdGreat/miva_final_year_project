export default function ConversationsPage() {
  return (
    <>
      <h1>Conversations</h1>
      <p style={{ color: "var(--muted)" }}>Review recent customer conversations and rate the bot's replies.</p>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Started</th>
              <th>Channel</th>
              <th>Language</th>
              <th>Turns</th>
              <th>Escalated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={6} style={{ color: "var(--muted)" }}>
                Conversations will appear here after Sprint 2 wires the persistence layer.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
