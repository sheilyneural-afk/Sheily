const controls = [
  ["Memoria", "Inspeccionar, autorizar o borrar recuerdos"],
  ["Consentimientos", "Revisar y revocar accesos por finalidad"],
  ["Delegaciones", "Limitar quién puede representarte"],
  ["Misiones", "Seguir decisiones, evidencia y apelaciones"],
];

export function App() {
  return (
    <main>
      <header><span className="eyebrow">NODO PERSONAL SOBERANO</span><h1>Tu mente no es telemetría.</h1><p>Esta consola muestra qué recuerda Noosfera, quién puede actuar y por qué.</p></header>
      <section>{controls.map(([title, text]) => <article key={title}><h2>{title}</h2><p>{text}</p><button type="button">Abrir</button></article>)}</section>
      <footer>Modo de referencia · Ningún actuador real conectado</footer>
    </main>
  );
}
