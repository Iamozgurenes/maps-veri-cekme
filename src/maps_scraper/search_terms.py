"""
Aranacak işletme/hizmet kategorileri.

Bu proje sadece klinikler için değil, Google Maps'te aranabilecek her türlü
hizmet işletmesi için kullanılacak şekilde tasarlanmıştır. `seed-jobs` komutuna
`--term` ile istediğiniz kadar özel terim verebilirsiniz (örn. "diş kliniği",
"kuaför", "oto yıkama"); hiç `--term` verilmezse aşağıdaki DEFAULT_CATEGORIES
listesi kullanılır.

Bu liste sadece pratik bir başlangıç noktasıdır, projeye özel ihtiyaca göre
serbestçe düzenlenebilir/genişletilebilir.
"""

DEFAULT_CATEGORIES: list[str] = [
    # Sağlık
    "klinik", "diş kliniği", "veteriner kliniği", "estetik kliniği",
    "fizik tedavi kliniği", "göz kliniği", "psikoloji kliniği", "eczane",
    # Güzellik & bakım
    "kuaför", "berber", "güzellik salonu", "spa", "masaj salonu",
    # Yeme-içme
    "restoran", "cafe", "pastane", "fırın",
    # Perakende & hizmet
    "market", "oto tamirci", "oto yıkama", "emlakçı", "avukat",
    "muhasebeci", "spor salonu", "otel",
]
