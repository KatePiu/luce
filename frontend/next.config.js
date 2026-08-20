/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Tutte le pagine sono componenti client-side (nessuna API route, nessuna
  // server action): il progetto può essere esportato come sito statico e
  // caricato via FTP su un hosting condiviso, oltre che pubblicato su Vercel.
  // Vedi README.md, sezione 6.4.
  output: "export",
  trailingSlash: true, // genera /chat/index.html invece di /chat.html: gli hosting condivisi servono index.html per cartella
  images: { unoptimized: true }, // l'ottimizzazione immagini di Next richiede un server, incompatibile con l'export statico
};

module.exports = nextConfig;
