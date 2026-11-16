import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { bozukHavuz } from "@/test/fikstur/ayarlar";
import {
  HavuzDiyalogu,
  havuzGovdesi,
  type HavuzGirdisi,
} from "./HavuzDiyalogu";

function kur(havuz = bozukHavuz) {
  const onGonder = vi.fn<(v: HavuzGirdisi) => void>();
  render(
    <HavuzDiyalogu
      havuz={havuz}
      gonderiliyor={false}
      hata={null}
      onGonder={onGonder}
      onKapat={() => {}}
    />,
  );
  return onGonder;
}

describe("HavuzDiyalogu (Faz 5b G1)", () => {
  it("taban × çarpanlar = Gider Toplamı canlı hesaplanır ve taban/çarpanlarla gönderilir", async () => {
    const u = userEvent.setup();
    const onGonder = kur();
    // Taban boşken toplam doğrudan girilir.
    expect(screen.getByLabelText("Toplam tutar (TL)")).toHaveValue("100000");
    await u.type(screen.getByLabelText("Taban tutar (TL)"), "1000");
    expect(
      screen.queryByLabelText("Toplam tutar (TL)"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("form-gider-toplami")).toHaveTextContent(
      "1.000,00 TL",
    );
    await u.click(screen.getByRole("button", { name: "Çarpan ekle" }));
    await u.type(screen.getByLabelText("Çarpan adı 1"), "SGK");
    await u.type(screen.getByLabelText("Çarpan 1"), "1,35");
    expect(screen.getByTestId("form-gider-toplami")).toHaveTextContent(
      "1.350,00 TL",
    );
    await u.click(screen.getByRole("button", { name: "Çarpan ekle" }));
    await u.type(screen.getByLabelText("Çarpan 2"), "1.3");
    expect(screen.getByTestId("form-gider-toplami")).toHaveTextContent(
      "1.755,00 TL",
    );
    // Dokunulmayan satırların payı korunur: TL tutarı yeni toplama göre yenilenir (1.755 × 0,3 = 526,5), pay %30 kalır.
    await waitFor(() =>
      expect(screen.getByLabelText("Tutar (TL) 1")).toHaveValue("526.5"),
    );
    await waitFor(() =>
      expect(screen.getByTestId("form-pay-1")).toHaveTextContent("30,0 %"),
    );
    await waitFor(() =>
      expect(screen.getByTestId("form-pay-toplam")).toHaveTextContent("56,7 %"),
    );
    await u.click(screen.getByRole("button", { name: "Çarpanı sil 2" }));
    expect(screen.getByTestId("form-gider-toplami")).toHaveTextContent(
      "1.350,00 TL",
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Tutar (TL) 1")).toHaveValue("405"),
    );
    // Elle değiştirilen satır toplam değişse de kendi TL tutarında kalır.
    const t2 = screen.getByLabelText("Tutar (TL) 2");
    await u.clear(t2);
    await u.type(t2, "945");
    await waitFor(() =>
      expect(screen.getByTestId("form-pay-2")).toHaveTextContent("70,0 %"),
    );
    await waitFor(() =>
      expect(screen.getByTestId("form-pay-toplam")).toHaveTextContent(
        "100,0 %",
      ),
    );
    await u.type(screen.getByLabelText("Neden"), "SGK zammı");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(onGonder).toHaveBeenCalledTimes(1)); // RHF gönderimi eşzamansız; yük altında bir tık gecikebilir
    const v = onGonder.mock.calls[0][0];
    expect(v.taban_tutar).toBe("1000");
    expect(v.toplam_tutar).toBeNull();
    expect(v.carpanlar).toEqual([{ ad: "SGK", deger: "1.35" }]);
    expect(v.anahtarlar).toEqual([
      { alt_kalem: "Dolum", pay_orani: "0.3", baz_miktar: "1" },
      { alt_kalem: "Etiketleme", tutar: "945", baz_miktar: "1" },
    ]);
    expect(havuzGovdesi(v)).toMatchObject({
      taban_tutar: "1000",
      carpanlar: [{ ad: "SGK", deger: "1.35" }],
    });
    expect(havuzGovdesi(v)).not.toHaveProperty("toplam_tutar");
  });

  it("tutar modunda pay % otomatik; alt kalemler tutarla gönderilir", async () => {
    const u = userEvent.setup();
    const onGonder = kur();
    expect(screen.getByRole("radio", { name: "Tutarla" })).toBeChecked();
    // 100.000 × 0,3 = 30.000 ve × 0,267 = 26.700 tutar olarak önceden doldurulur.
    expect(screen.getByLabelText("Tutar (TL) 1")).toHaveValue("30000");
    expect(screen.getByLabelText("Tutar (TL) 2")).toHaveValue("26700");
    await waitFor(() =>
      expect(screen.getByTestId("form-pay-1")).toHaveTextContent("30,0 %"),
    );
    await waitFor(() =>
      expect(screen.getByTestId("form-pay-toplam")).toHaveTextContent("56,7 %"),
    );
    const t2 = screen.getByLabelText("Tutar (TL) 2");
    await u.clear(t2);
    await u.type(t2, "70000");
    await waitFor(() =>
      expect(screen.getByTestId("form-pay-2")).toHaveTextContent("70,0 %"),
    );
    await waitFor(() =>
      expect(screen.getByTestId("form-pay-toplam")).toHaveTextContent(
        "100,0 %",
      ),
    );
    await u.type(screen.getByLabelText("Neden"), "Aralık bütçesi");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(onGonder).toHaveBeenCalledTimes(1)); // RHF gönderimi eşzamansız; yük altında bir tık gecikebilir
    const v = onGonder.mock.calls[0][0];
    expect(v.toplam_tutar).toBe("100000");
    expect(v.taban_tutar).toBeNull();
    // Dokunulmayan satır özgün payıyla gider (yuvarlama kayması olmasın); değişen satır tutarla gider.
    expect(v.anahtarlar).toEqual([
      { alt_kalem: "Dolum", pay_orani: "0.3", baz_miktar: "1" },
      { alt_kalem: "Etiketleme", tutar: "70000", baz_miktar: "1" },
    ]);
  });

  it("Yüzdeyle moduna geçince paylar dolar ve pay_orani ile gönderilir; alt kalem eklenip silinebilir", async () => {
    const u = userEvent.setup();
    const onGonder = kur();
    await u.click(screen.getByRole("radio", { name: "Yüzdeyle" }));
    expect(screen.getByLabelText("Pay (%) 1")).toHaveValue("30");
    expect(screen.getByLabelText("Pay (%) 2")).toHaveValue("26.7");
    await u.click(screen.getByRole("button", { name: "Alt kalem ekle" }));
    await u.type(screen.getByLabelText("Alt kalem 3"), "Torba");
    await u.type(screen.getByLabelText("Pay (%) 3"), "43,3");
    await waitFor(() =>
      expect(screen.getByTestId("form-pay-toplam")).toHaveTextContent(
        "100,0 %",
      ),
    );
    await u.click(screen.getByRole("button", { name: "Alt kalemi sil 1" }));
    await waitFor(() =>
      expect(screen.getByTestId("form-pay-toplam")).toHaveTextContent("70,0 %"),
    );
    await u.type(screen.getByLabelText("Neden"), "yeni hat");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    const onay = await screen.findByRole("dialog", {
      name: "Pay toplamı %100 değil",
    });
    await u.click(within(onay).getByRole("button", { name: "Yine de kaydet" }));
    const v = onGonder.mock.calls[0][0];
    expect(v.anahtarlar).toEqual([
      { alt_kalem: "Etiketleme", pay_orani: "0.267", baz_miktar: "1" },
      { alt_kalem: "Torba", pay_orani: "0.433", baz_miktar: "1" },
    ]);
  });

  it("Yüzdeyle düzenlenip Tutarla'ya dönülen satır düzenlemesini korur", async () => {
    const u = userEvent.setup();
    const onGonder = kur();
    await u.click(screen.getByRole("radio", { name: "Yüzdeyle" }));
    const p1 = screen.getByLabelText("Pay (%) 1");
    await u.clear(p1);
    await u.type(p1, "50");
    await u.click(screen.getByRole("radio", { name: "Tutarla" }));
    expect(screen.getByLabelText("Tutar (TL) 1")).toHaveValue("50000");
    await u.type(screen.getByLabelText("Neden"), "x");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    const onay = await screen.findByRole("dialog", {
      name: "Pay toplamı %100 değil",
    });
    await u.click(within(onay).getByRole("button", { name: "Yine de kaydet" }));
    expect(onGonder.mock.calls[0][0].anahtarlar[0]).toEqual({
      alt_kalem: "Dolum",
      tutar: "50000",
      baz_miktar: "1",
    });
    expect(onGonder.mock.calls[0][0].anahtarlar[1]).toEqual({
      alt_kalem: "Etiketleme",
      pay_orani: "0.267",
      baz_miktar: "1",
    });
  });

  it("tutar modunda boş tutar ve geçersiz çarpan hata verir", async () => {
    const u = userEvent.setup();
    const onGonder = kur();
    await u.clear(screen.getByLabelText("Tutar (TL) 1"));
    await u.type(screen.getByLabelText("Taban tutar (TL)"), "100");
    await u.click(screen.getByRole("button", { name: "Çarpan ekle" }));
    await u.type(screen.getByLabelText("Çarpan 1"), "0");
    await u.type(screen.getByLabelText("Neden"), "x");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    // Zod çözücüsü eşzamansız; yük altında 1 sn'yi aşabiliyor (tam süit koşusunda görüldü).
    expect(
      await screen.findByText(
        "Çarpan 0'dan büyük olmalı",
        {},
        { timeout: 5000 },
      ),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("Sayı olmalı", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(onGonder).not.toHaveBeenCalled();
  }, 20_000); // çok adımlı form; tam süit yükünde 5 sn varsayılanı aşabiliyor
});
