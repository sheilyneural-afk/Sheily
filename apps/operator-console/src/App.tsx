const services = ["EXP", "IDN", "MEM", "PER", "COG", "AGY", "GOV", "EXE", "FED", "SEC", "AUD", "EVO", "TMP", "RES"];

export function App() {
  return <main><header><div><span>NOOSFERA / CONTROL</span><h1>Estado del nodo</h1></div><button type="button">PARADA SEGURA</button></header><section className="summary"><article><b>14</b><span>dominios</span></article><article><b>0</b><span>actuadores reales</span></article><article><b>OK</b><span>canal de parada</span></article></section><section className="grid">{services.map((service) => <article className="service" key={service}><i /><strong>{service}</strong><small>reference-ready</small></article>)}</section></main>;
}
