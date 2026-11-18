"""Pilot (tek bilgisayar) kurulum paketini hazırlar. Geliştirme klasöründe HİÇBİR ŞEYİ silmez ya da değiştirmez; yalnız okur.

Pakete girenler: uygulama kodu (git'te izlenen backend/, fiyat_motoru/, kurulum/ betikleri, pyproject.toml), ilk Genel Direktör betiği,
derlenmiş arayüz (frontend/dist), Excel şablonları (sablonlar/*.xlsx, uygulama "Şablonu indir" için kullanır) ve rehberleri,
kurulum ve kullanım rehberleri, internet gerektirmeyen Python bağımlılıkları (kurulum/paketler) ve Python 3.12 kurulum dosyası,
çift tıklanan .bat dosyaları ve OKU-BENI.pdf.
Girmeyenler: veri/ (şirket verisi), testler, test-dongusu, deneme betikleri, eski planlar, kök klasördeki Excel'ler, .git, .venv, node_modules.

Kullanım (proje kökünden; önce `cd frontend && npx vite build`):
    .venv/Scripts/python scripts/11-18-2026-pilot-paketi-hazirla.py [--hedef <klasör>] [--zip]
"""
import argparse
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
PYTHON_SURUM = "3.12.10"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_SURUM}/python-{PYTHON_SURUM}-amd64.exe"

# git'te izlenen ve pakete girecek yollar (önek eşleşmesi)
IZLENEN = ("backend/", "fiyat_motoru/", "kurulum/", "pyproject.toml", "scripts/11-04-2026-ilk-genel-direktor.py",
           "docs/11-12-2026-kurulum-ve-isletim-rehberi.md", "sablonlar/11-16-2026-sablonlar-rehberi.pdf",
           "sablonlar/11-16-2026-sablonlar-rehberi.md")
HARIC = ("kurulum/pilot/", "__pycache__")


def git_dosyalari() -> list[str]:
    cikti = subprocess.run(["git", "ls-files"], cwd=KOK, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return [d for d in cikti.splitlines() if d.startswith(IZLENEN) and not any(h in d for h in HARIC)]


def kopyala(kaynak: Path, hedef: Path) -> None:
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(kaynak, hedef)


def crlf(yol: Path) -> None:
    t = yol.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    yol.write_bytes(t)


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--hedef", default=str(Path.home() / "Desktop" / "11-18-2026-FiyatCalismasi-Pilot"))
    a.add_argument("--zip", action="store_true")
    g = a.parse_args()
    hedef = Path(g.hedef).resolve()
    if hedef.exists():
        raise SystemExit(f"Hedef klasör zaten var, üzerine yazılmaz: {hedef}")
    if KOK in hedef.parents or hedef == KOK:
        raise SystemExit("Hedef, proje klasörünün içinde olamaz.")
    dist = KOK / "frontend" / "dist" / "index.html"
    if not dist.exists():
        raise SystemExit("frontend/dist yok; önce `cd frontend && npx vite build` çalıştırın.")

    # 1. Kod (git'te izlenen hâli, çalışma ağacından)
    dosyalar = git_dosyalari()
    for d in dosyalar:
        kopyala(KOK / d, hedef / d)
    print(f"kod: {len(dosyalar)} dosya")

    # 2. Derlenmiş arayüz
    shutil.copytree(KOK / "frontend" / "dist", hedef / "frontend" / "dist")
    print("arayüz: frontend/dist")

    # 3. Excel şablonları (git dışı ama uygulama kullanır)
    sablonlar = sorted((KOK / "sablonlar").glob("11-16-2026-[0-9][0-9]-*.xlsx"))
    if len(sablonlar) < 16:
        raise SystemExit(f"Beklenen 16 şablon yerine {len(sablonlar)} bulundu; sablonlar/uret.py ile üretin.")
    for s in sablonlar:
        kopyala(s, hedef / "sablonlar" / s.name)
    print(f"şablonlar: {len(sablonlar)} xlsx")

    # 4. Kullanım rehberi (en yeni sürüm)
    rehberler = sorted((KOK / "docs" / "ozel").glob("*-kullanim-rehberi.html"))
    if rehberler:
        kopyala(rehberler[-1], hedef / "docs" / rehberler[-1].name)
        print(f"rehber: {rehberler[-1].name}")
    (hedef / "docs" / "11-12-2026-kurulum-ve-isletim-rehberi.md").exists() or print("UYARI: kurulum rehberi yok")

    # 5. Python bağımlılıkları (internetsiz kurulum için) + Python kurulum dosyası
    paket = hedef / "kurulum" / "paketler"
    paket.mkdir(parents=True, exist_ok=True)
    bagimliliklar = tomllib.loads((KOK / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    # Sürümler geliştirme ortamındakilere sabitlenir (test edilen sürümler); kısıt = geliştirme ortamının pip freeze çıktısı
    kisit = paket / "_kisit.txt"
    donmus = subprocess.run([sys.executable, "-m", "pip", "freeze", "--disable-pip-version-check"], capture_output=True, text=True, check=True).stdout
    kisit.write_text("\n".join(x for x in donmus.splitlines() if "==" in x and not x.startswith("-e")) + "\n", encoding="utf-8")
    istek = paket / "_istek.txt"
    istek.write_text("\n".join(bagimliliklar) + "\n", encoding="utf-8")
    kod = subprocess.run([sys.executable, "-m", "pip", "download", "--disable-pip-version-check", "--only-binary=:all:",
                          "--platform", "win_amd64", "--python-version", "3.12", "--implementation", "cp",
                          "-r", str(istek), "-c", str(kisit), "-d", str(paket)], cwd=KOK).returncode
    if kod != 0:
        raise SystemExit("pip download başarısız.")
    sabit = [f"{w.name.split('-')[0].replace('_', '-')}=={w.name.split('-')[1]}" for w in sorted(paket.glob("*.whl"))]
    (paket / "gereksinimler.txt").write_text("\n".join(sabit) + "\n", encoding="utf-8")
    kisit.unlink()
    istek.unlink()
    print(f"bağımlılıklar: {len(list(paket.glob('*.whl')))} paket")
    exe = paket / f"python-{PYTHON_SURUM}-amd64.exe"
    urllib.request.urlretrieve(PYTHON_URL, exe)
    print(f"Python kurulum dosyası: {exe.name} ({exe.stat().st_size // 1_000_000} MB)")

    # 6. Çift tıklanan dosyalar ve OKU-BENI
    for bat in sorted((KOK / "kurulum" / "pilot").glob("*.bat")):
        kopyala(bat, hedef / bat.name)
        crlf(hedef / bat.name)
    oku = KOK / "kurulum" / "pilot" / "11-18-2026-oku-beni.html"
    pdf = hedef / "11-18-2026-OKU-BENI.pdf"
    js = ("const { chromium } = require(process.argv[1]);"
          "(async()=>{const b=await chromium.launch();const p=await b.newPage();"
          "await p.goto('file:///'+process.argv[2].replace(/\\\\/g,'/'));"
          "await p.pdf({path:process.argv[3],format:'A4',printBackground:true});await b.close();})();")
    pw = str(KOK / "frontend" / "node_modules" / "@playwright" / "test")
    if subprocess.run(["node", "-e", js, pw, str(oku), str(pdf)]).returncode != 0 or not pdf.exists():
        kopyala(oku, hedef / "11-18-2026-OKU-BENI.html")
        print("UYARI: PDF üretilemedi, OKU-BENI HTML olarak kondu")
    else:
        print("OKU-BENI.pdf")

    # 7. Denetim: pakette olmaması gerekenler
    yasak = [p for p in hedef.rglob("*") if re.search(r"(\.db|\.db-wal|\.db-shm)$|[\\/](veri|tests|test-dongusu|node_modules|\.venv|\.git)[\\/]", str(p))]
    if yasak:
        raise SystemExit(f"Pakete girmemesi gereken dosya var: {yasak[:5]}")
    boyut = sum(p.stat().st_size for p in hedef.rglob("*") if p.is_file())
    print(f"Paket hazır: {hedef} ({boyut // 1_000_000} MB)")
    if g.zip:
        z = shutil.make_archive(str(hedef), "zip", root_dir=hedef.parent, base_dir=hedef.name)
        print(f"zip: {z}")


if __name__ == "__main__":
    main()
