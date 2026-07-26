export function SessionLoading() {
  return (
    <main className="auth-shell">
      <section className="auth-card auth-card--loading" aria-live="polite">
        <div className="auth-brand">
          <span className="brand__name">MK-VIP</span>
          <span className="brand__description">
            MK Value Investing Platform
          </span>
        </div>
        <p>Vérification de votre session…</p>
      </section>
    </main>
  );
}
