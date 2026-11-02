import { Moon, Sun } from "lucide-react";
import { useState } from "react";
import { Button } from "@/bilesenler/ui/button";
import { ilkTema, temaUygula, type Tema } from "@/yardimcilar/tema";

export function TemaAnahtari() {
  const [tema, setTema] = useState<Tema>(() => ilkTema());
  const degistir = () => {
    const yeni: Tema = tema === "dark" ? "light" : "dark";
    temaUygula(yeni);
    setTema(yeni);
  };
  return (
    <Button
      variant="outline"
      size="icon"
      onClick={degistir}
      aria-label={tema === "dark" ? "Açık temaya geç" : "Koyu temaya geç"}
      title={tema === "dark" ? "Açık tema" : "Koyu tema"}
    >
      {tema === "dark" ? <Sun /> : <Moon />}
    </Button>
  );
}
