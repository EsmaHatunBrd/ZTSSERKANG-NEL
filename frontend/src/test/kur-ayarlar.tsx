import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";

/** Sayfayı sorgu istemcisi, yönlendirici ve senaryo bağlamıyla çizer (varsayılan senaryo 1). */
export function kurSayfa(eleman: ReactElement, senaryo = 1) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/?senaryo=${senaryo}`]}>
        <SenaryoSaglayici>{eleman}</SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
