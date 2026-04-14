import Link from "next/link";

export default function NotFound() {
  return (
    <main style={{ margin: 40, fontFamily: "Arial, sans-serif" }}>
      <h1>Page not found</h1>
      <p>
        <Link href="/">Back to portfolio overview</Link>
      </p>
    </main>
  );
}
