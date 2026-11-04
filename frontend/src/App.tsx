import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { RouterProvider } from "react-router-dom";
import { GirisKapisi } from "@/bilesenler/GirisKapisi";
import { TooltipProvider } from "@/bilesenler/ui/tooltip";
import { sorguIstemcisi } from "./api/sorguIstemcisi";
import { yonlendirici } from "./yonlendirme";

export default function App() {
  const [istemci] = useState(() => sorguIstemcisi());
  const [yon] = useState(() => yonlendirici());
  return (
    <QueryClientProvider client={istemci}>
      <TooltipProvider>
        <GirisKapisi>
          <RouterProvider router={yon} />
        </GirisKapisi>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
