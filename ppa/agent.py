from google.adk.agents.llm_agent import Agent

from .inventory import (
    find_storage_locations,
    get_part_interchangeability,
    list_sites_warehouses_bins,
    map_parts_to_equipment,
    search_parts,
)
from .procurement import (
    create_purchase_order,
    list_available_vendors,
    log_goods_receipt,
    lookup_vendors,
    track_incoming_shipments,
    track_purchase_orders,
    update_purchase_order_status,
)
from .stock import (
    check_stock_availability,
    get_stock_parameters,
    search_serial_batches,
    set_stock_batch_status,
    update_reorder_parameters,
)

LLM_MODEL = "gemini-3.5-flash-lite"

inventory_agent = Agent(
    model=LLM_MODEL,
    name="inventory_agent",
    description="Mencari katalog suku cadang, pemetaan peralatan, dan lokasi penyimpanan.",
    instruction=(
        "Gunakan alat katalog suku cadang untuk menjawab pertanyaan tentang SKU, nomor "
        "suku cadang OEM, komponen, suku cadang pengganti, kecocokan peralatan, "
        "penyimpanan, suku cadang kritis, dan penanda bahan berbahaya. Data penggantian "
        "tidak mencatat status persetujuan, dan instruksi penanganan bahan berbahaya "
        "atau referensi SDS tidak tersedia dalam skema."
    ),
    tools=[
        search_parts,
        get_part_interchangeability,
        map_parts_to_equipment,
        find_storage_locations,
    ],
)

stock_agent = Agent(
    model=LLM_MODEL,
    name="stock_agent",
    description="Memeriksa saldo stok, parameter pemesanan ulang, dan data nomor seri/batch.",
    instruction=(
        "Gunakan alat stok untuk memeriksa jumlah terkini, mencari nomor seri/batch, "
        "dan melihat status karantina. Jumlah tersedia dihitung dari jumlah stok "
        "dikurangi jumlah yang telah dipesan; skema tidak mencatat jumlah per batch "
        "yang dikarantina. Ubah parameter pemesanan ulang atau status batch hanya "
        "jika diminta secara eksplisit."
    ),
    tools=[
        get_stock_parameters,
        update_reorder_parameters,
        check_stock_availability,
        search_serial_batches,
        set_stock_batch_status,
    ],
)

procurement_agent = Agent(
    model=LLM_MODEL,
    name="procurement_agent",
    description="Melacak pesanan pembelian dan pemasok, membuat pesanan pembelian, serta mencatat penerimaan barang.",
    instruction=(
        "Gunakan alat pengadaan untuk menampilkan pemasok yang tersedia, memeriksa "
        "detail pemasok, status pesanan pembelian, waktu tunggu pemasok, perkiraan "
        "tanggal pengiriman, dan penerimaan barang. Skema tidak mencatat permintaan "
        "pembelian, manifes pengiriman, atau metode pengiriman."
    ),
    tools=[
        track_purchase_orders,
        track_incoming_shipments,
        list_available_vendors,
        lookup_vendors,
        create_purchase_order,
        update_purchase_order_status,
        log_goods_receipt,
    ],
)

root_agent = Agent(
    model=LLM_MODEL,
    name="root_agent",
    description="Asisten inventaris dan pengadaan untuk pemeliharaan pertambangan.",
    instruction=(
        "Arahkan pertanyaan tentang katalog, model peralatan, penyimpanan, dan "
        "penggantian suku cadang ke agen inventaris; pertanyaan tentang saldo stok, "
        "nomor seri/batch, karantina, dan pemesanan ulang ke agen stok; serta pertanyaan "
        "tentang PO, pemasok, tanggal pengiriman, dan penerimaan barang ke agen pengadaan. "
        "Skema tidak menyimpan kecocokan untuk aset tertentu, persetujuan penggantian, "
        "informasi penanganan/SDS, reservasi, pergerakan stok, permintaan pembelian, "
        "atau manifes pengiriman. Gunakan list_sites_warehouses_bins untuk menampilkan "
        "hierarki lokasi, gudang, dan bin. Gunakan alat agen spesialis untuk mendapatkan "
        "informasi operasional dan jangan menebak."
    ),
    tools=[list_sites_warehouses_bins],
    sub_agents=[inventory_agent, stock_agent, procurement_agent],
)
