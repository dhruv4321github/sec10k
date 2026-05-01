# Sample API Requests and Responses

## Prerequisites

### 1. Environment setup

Create a `.env` file in the project root with:

```env
OPENAI_API_KEY=sk-...
SEC_USER_AGENT="YourName your@email.com"
```

### 2. Start the backend

```bash
docker compose up -d
```

This starts three services:

| Service    | Port | Description                        |
|------------|------|------------------------------------|
| `db`       | 5432 | PostgreSQL 16 with pgvector        |
| `backend`  | 8000 | FastAPI backend                    |
| `frontend` | 3000 | React frontend                     |

### 3. Verify the backend is healthy

```bash
curl http://localhost:8000/healthz
```

```json
{"status": "ok"}
```

Once healthy, you can run any of the commands below. All examples use `http://localhost:8000`.

---

## 1. Ingest a 10-K — `POST /documents/ingest`

Ingestion is asynchronous. The endpoint returns HTTP 202 immediately and processes the filing in the background (fetch HTML from SEC EDGAR → parse → extract sections → chunk → embed).

### Ingest Apple Inc. (AAPL) 2025 10-K

```bash
curl -X POST http://localhost:8000/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
    "company": "Apple Inc.",
    "ticker": "AAPL",
    "fiscal_year": 2025
  }'
```

Response (HTTP 202 Accepted):

```json
{
    "id": "febc608c-23d9-49f3-9bcd-a5119aa0bc65",
    "company": "Apple Inc.",
    "ticker": "AAPL",
    "cik": "320193",
    "accession": "0000320193-25-000079",
    "fiscal_year": 2025,
    "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
    "status": "pending",
    "error": null,
    "raw_text_chars": 0,
    "chunk_count": 0,
    "created_at": "2026-05-01T02:28:04.938413Z",
    "updated_at": "2026-05-01T02:28:04.938413Z"
}
```

### Ingest NVIDIA Corporation (NVDA) 2025 10-K

```bash
curl -X POST http://localhost:8000/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm",
    "company": "NVIDIA Corporation",
    "ticker": "NVDA",
    "fiscal_year": 2025
  }'
```

Response (HTTP 202 Accepted):

```json
{
    "id": "c87ef81e-c496-4b5a-9946-8284ff1960bd",
    "company": "NVIDIA Corporation",
    "ticker": "NVDA",
    "cik": "1045810",
    "accession": "0001045810-25-000023",
    "fiscal_year": 2025,
    "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm",
    "status": "pending",
    "error": null,
    "raw_text_chars": 0,
    "chunk_count": 0,
    "created_at": "2026-05-01T17:25:26.714921Z",
    "updated_at": "2026-05-01T17:25:26.714921Z"
}
```

Poll `GET /documents/{id}` until `status` reaches `"ready"` (typically 5–15 seconds). Once ready, `raw_text_chars` and `chunk_count` are populated (e.g., Apple: 205,366 chars / 65 chunks; NVIDIA: 346,624 chars / 73 chunks).

---

## 2. List documents — `GET /documents`

```bash
curl http://localhost:8000/documents
```

Response:

```json
[
    {
        "id": "c87ef81e-c496-4b5a-9946-8284ff1960bd",
        "company": "NVIDIA Corporation",
        "ticker": "NVDA",
        "cik": "1045810",
        "accession": "0001045810-25-000023",
        "fiscal_year": 2025,
        "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm",
        "status": "ready",
        "error": null,
        "raw_text_chars": 346624,
        "chunk_count": 73,
        "created_at": "2026-05-01T17:25:26.714921Z",
        "updated_at": "2026-05-01T17:25:30.516552Z"
    },
    {
        "id": "febc608c-23d9-49f3-9bcd-a5119aa0bc65",
        "company": "Apple Inc.",
        "ticker": "AAPL",
        "cik": "320193",
        "accession": "0000320193-25-000079",
        "fiscal_year": 2025,
        "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
        "status": "ready",
        "error": null,
        "raw_text_chars": 205366,
        "chunk_count": 65,
        "created_at": "2026-05-01T02:28:04.938413Z",
        "updated_at": "2026-05-01T02:28:08.491884Z"
    }
]
```

---

## 3. Get sections of a document — `GET /documents/{id}/sections`

The parser extracts four key sections from each 10-K filing: Item 1 (Business), Item 1A (Risk Factors), Item 7 (MD&A), and Item 8 (Financial Statements). This endpoint returns all sections with their full text.

```bash
curl http://localhost:8000/documents/febc608c-23d9-49f3-9bcd-a5119aa0bc65/sections
```

Response (section texts truncated for brevity):

```json
{
    "document_id": "febc608c-23d9-49f3-9bcd-a5119aa0bc65",
    "company": "Apple Inc.",
    "sections": [
        {
            "id": "3fc00b8a-0c75-483e-a361-e339956665cb",
            "name": "Business",
            "item_label": "Item 1",
            "char_count": 16009,
            "text": "Item 1. Business\n\nCompany Background\nThe Company designs, manufactures and markets smartphones, personal computers, tablets, wearables and accessories, and sells a variety of related services. ..."
        },
        {
            "id": "dd31d932-1452-4069-a5c8-6ded4714829e",
            "name": "Risk Factors",
            "item_label": "Item 1A",
            "char_count": 68057,
            "text": "Item 1A. Risk Factors\n\nThe Company's business, reputation, results of operations, financial condition and stock price can be affected by a number of factors, ..."
        },
        {
            "id": "9cc52e50-2553-42b8-a957-bff3af2dd223",
            "name": "Management's Discussion and Analysis",
            "item_label": "Item 7",
            "char_count": 17891,
            "text": "Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations\n\nFiscal Year Highlights\nTotal net sales increased 5% or $19.2 billion during 2025 ..."
        },
        {
            "id": "f4a5c7b1-fbf5-4448-9eab-de4105c41bab",
            "name": "Financial Statements",
            "item_label": "Item 8",
            "char_count": 60183,
            "text": "Item 8. Financial Statements and Supplementary Data\n\nAll financial amounts in this Item 8 are expressed in millions, ..."
        }
    ]
}
```

---

## 3b. Get a single section — `GET /documents/{id}/sections/{section_name}`

Convenience endpoint to fetch a single section by name, if you don't need all four at once:

```bash
curl http://localhost:8000/documents/febc608c-23d9-49f3-9bcd-a5119aa0bc65/sections/Business
```

Response:

```json
{
    "id": "3fc00b8a-0c75-483e-a361-e339956665cb",
    "document_id": "febc608c-23d9-49f3-9bcd-a5119aa0bc65",
    "name": "Business",
    "item_label": "Item 1",
    "text": "Item 1. Business\n\nCompany Background\nThe Company designs, manufactures and markets smartphones, personal computers, tablets, wearables and accessories, and sells a variety of related services. The Company’s fiscal year is the 52- or 53-week period that ends on the last Saturday of September.\n\nProducts\niPhone\niPhone® is the Company’s line of smartphones based on its iOS operating system. The iPhone line includes iPhone 17 Pro, iPhone Air™, iPhone 17, iPhone 16 and iPhone 16e.\nMac\nMac® is the Company’s line of personal computers based on its macOS® operating system. The Mac line includes laptops MacBook Air® and MacBook Pro®, as well as desktops iMac®, Mac mini®, Mac Studio® and Mac Pro®.\niPad\niPad® is the Company’s line of multipurpose tablets based on its iPadOS® operating system. The iPad line includes iPad Pro®, iPad Air®, iPad and iPad mini®.\nWearables, Home and Accessories\nWearables includes smartwatches, wireless headphones and spatial computers. The Company’s line of smartwatches, based on its watchOS® operating system, includes Apple Watch® Series 11, Apple Watch SE® 3 and Apple Watch Ultra® 3. The Company’s line of wireless headphones includes AirPods®, AirPods Pro®, AirPods Max® and Beats® products. Apple Vision Pro™ is the Company’s spatial computer based on its visionOS® operating system.\nHome includes Apple TV 4K®, the Company’s media streaming and gaming device based on its tvOS® operating system, and HomePod® and HomePod mini®, high-fidelity wireless smart speakers.\nAccessories includes Apple-branded and third-party accessories.\nApple Inc. | 2025 Form 10-K | 1\n\nServices\nAdvertising\nThe Company’s advertising services include third-party licensing arrangements and the Company’s own advertising platforms.\nAppleCare\nThe Company offers a portfolio of fee-based service and support products under the AppleCare® brand. The offerings provide priority access to Apple technical support, access to the global Apple authorized service network for repair and replacement services, and in many cases additional coverage for instances of accidental damage or theft and loss, depending on the country and type of product.\nCloud Services\nThe Company’s cloud services store and keep customers’ content up-to-date and available across multiple Apple devices and Windows personal computers.\nDigital Content\nThe Company operates various platforms, including the App Store®, that allow customers to discover and download applications and digital content, such as books, music, video, games and podcasts.\nThe Company also offers digital content through subscription-based services, including Apple Arcade®, a game service; Apple Fitness+®, a personalized fitness service; Apple Music®, which offers users a curated listening experience with on-demand radio stations; Apple News+®, a news and magazine service; and Apple TV®, which offers exclusive original content and live sports.\nPayment Services\nThe Company offers payment services, including Apple Card®, a co-branded credit card, and Apple Pay®, a cashless payment service.\n\nSegments\nThe Company manages its business primarily on a geographic basis. The Company’s reportable segments consist of the Americas, Europe, Greater China, Japan and Rest of Asia Pacific. Americas includes both North and South America. Europe includes European countries, as well as India, the Middle East and Africa. Greater China includes China mainland, Hong Kong and Taiwan. Rest of Asia Pacific includes Australia, New Zealand and those Asian countries not included in the Company’s other reportable segments. Although the reportable segments provide similar hardware and software products and similar services, each one is managed separately to better align with the location of the Company’s customers and distribution partners and the unique market dynamics of each geographic region.\n\nMarkets and Distribution\nThe Company’s customers are primarily in the consumer, small and mid-sized business, education, enterprise and government markets. The Company sells its products and resells third-party products in most of its major markets directly to customers through its retail and online stores and its direct sales force. The Company sells its services in the same markets through its various service platforms. The Company also employs a variety of indirect distribution channels, such as third-party cellular network carriers and other resellers, for the sale of its products and certain of its services. During 2025, the Company’s net sales through its direct and indirect distribution channels accounted for 40% and 60%, respectively, of total net sales.\n\nCompetition\nThe markets for the Company’s products and services are highly competitive and are characterized by aggressive price competition, downward pressure on gross margins, continual improvement in product performance, and price sensitivity on the part of consumers and businesses. The markets in which the Company competes are further defined by frequent introduction of new products and services, short product life cycles, evolving industry standards, and rapid adoption of technological advancements by competitors. Many of the Company’s competitors seek to compete primarily through aggressive pricing and very low cost structures, and by imitating the Company’s products and infringing on its intellectual property.\nApple Inc. | 2025 Form 10-K | 2\n\nThe Company’s ability to compete successfully depends heavily on ensuring the continuing and timely introduction of innovative new products, services and technologies to the marketplace. The Company designs and develops nearly the entire solution for its products, including the hardware, operating system, numerous software applications and related services. Principal competitive factors important to the Company include price, product and service features (including security features), relative price and performance, product and service quality and reliability, design and technology innovation, a strong third-party software and accessories ecosystem, marketing and distribution capability, service and support, corporate reputation, and the ability to effectively protect and enforce the Company’s intellectual property rights.\nThe Company is focused on expanding its market opportunities related to smartphones, personal computers, tablets, wearables and accessories, and services. The Company’s products and services face substantial competition from companies that have significant technical, marketing, distribution and other resources, as well as established hardware, software, and service offerings with large customer bases. In addition, the Company faces significant competition as competitors imitate the Company’s product features and applications within their products to offer more competitive solutions. The Company also expects competition to intensify as competitors imitate the Company’s approach to providing components seamlessly within their offerings or work collaboratively to offer integrated solutions. Some of the Company’s competitors have broad product lines, low-priced products, large installed bases of active devices, and large customer bases. Competition has been particularly intense as competitors have aggressively cut prices and lowered product margins. Certain competitors have the resources, experience or cost structures to provide products and services at little or no profit or even at a loss. The Company has a minority market share in the global smartphone, personal computer, tablet and wearables markets, and some of the markets in which the Company competes have from time to time experienced little to no growth or contracted overall.\n\nSupply of Components\nAlthough most components essential to the Company’s business are generally available from multiple sources, certain components are currently obtained from single or limited sources. The Company also competes for various components with other participants in the markets for smartphones, personal computers, tablets, wearables and accessories. Therefore, many components used by the Company, including those that are available from multiple sources, are at times subject to industry-wide shortage and significant commodity pricing fluctuations. Restrictions on international trade can increase the cost or limit the availability of the Company’s products and the components and rare earths and other raw materials that go into them.\nThe Company uses some custom components that are not commonly used by its competitors, and new products introduced by the Company often utilize custom components available from only one source. When a component or product uses new technologies, initial capacity constraints may exist until the suppliers’ yields have matured or their manufacturing capacities have increased. The Company has entered into agreements for the supply of many components; however, the Company may not be able to extend or renew agreements for the supply of components on similar terms, or at all, and may not be successful in obtaining sufficient quantities from its suppliers or in a timely manner, or in identifying and obtaining sufficient quantities from an alternative source. In addition, component suppliers may fail, be subject to consolidation within a particular industry, or decide to concentrate on the production of common components instead of components customized to meet the Company’s requirements, further limiting the Company’s ability to obtain sufficient quantities of components on commercially reasonable terms, or at all.\n\nResearch and Development\nBecause the industries in which the Company competes are characterized by rapid technological advances, the Company’s ability to compete successfully depends heavily upon its ability to ensure a continual and timely flow of competitive products, services and technologies to the marketplace. The Company continues to develop new technologies to enhance existing products and services, and to expand the range of its offerings through research and development (“R&D”), licensing of intellectual property and acquisition of third-party businesses and technology.\n\nIntellectual Property\nThe Company currently holds a broad collection of intellectual property rights relating to certain aspects of its hardware, software and services. This includes patents, designs, copyrights, trademarks, trade secrets and other forms of intellectual property rights in the U.S. and various foreign countries. Although the Company believes the ownership of such intellectual property rights is an important factor in differentiating its business and that its success does depend in part on such ownership, the Company relies primarily on the innovative skills, technical competence and marketing abilities of its personnel.\nThe Company regularly files patent, design, copyright and trademark applications to protect innovations arising from its hardware, software and service research, development, design and marketing, and is currently pursuing thousands of applications around the world. Over time, the Company has accumulated a large portfolio of issued and registered intellectual property rights around the world. No single intellectual property right is solely responsible for protecting the Company’s products and services. The Company believes the duration of its intellectual property rights is adequate relative to the expected lives of its products and services.\nApple Inc. | 2025 Form 10-K | 3\n\nIn addition to Company-owned intellectual property, many of the Company’s products and services include technology or intellectual property that must be licensed from third parties. It may be necessary in the future to seek or renew licenses relating to various aspects of the Company’s products, processes and services. While the Company has generally been able to obtain such licenses on commercially reasonable terms in the past, there is no guarantee that such licenses could be obtained in the future on reasonable terms or at all.\n\nBusiness Seasonality and Product Introductions\nThe Company has historically experienced higher net sales in its first quarter compared to other quarters in its fiscal year due in part to seasonal holiday demand. Additionally, new product and service introductions can significantly impact net sales, cost of sales and operating expenses. The timing of product introductions can also impact the Company’s net sales to its indirect distribution channels as these channels are filled with new inventory following a product launch, and channel inventory of an older product often declines as the launch of a newer product approaches. Net sales can also be affected when consumers and distributors anticipate a product introduction.\n\nHuman Capital\nThe Company believes that its people play an important role in its success, and strives to attract, develop and retain the best talent. The Company works to create a culture of collaboration, one where people with a broad range of backgrounds and perspectives can come together to innovate and do the best work of their lives. The Company is an equal opportunity employer committed to inclusion and to providing a workplace free of harassment or discrimination. As of September 27, 2025, the Company had approximately 166,000 full-time equivalent employees.\nThe Company believes that compensation should be competitive and equitable, and offers discretionary cash and equity awards to enable employees to share in the Company’s success. The Company recognizes its people are most likely to thrive when they have the resources to meet their needs and the time and support to succeed in their professional and personal lives. In support of this, the Company offers a wide variety of benefits for employees around the world, including health, wellness and time away.\nThe Company invests in resources to help its people develop and achieve their career goals. The Company offers programs through Apple University on leadership, management and influence, as well as Apple culture and values. Team members can also take advantage of online classes for business, technical and personal development.\nThe Company believes that open and honest communication among team members, managers and leaders helps create an open, collaborative work environment where everyone can contribute, grow and succeed. Team members are encouraged to come to their managers with questions, feedback or concerns, and the Company conducts surveys that gauge employee sentiment in areas like career development, manager performance and inclusion.\nThe Company is committed to the safety and security of its team members everywhere it operates. The Company supports employees with general safety, security and crisis management training, and by putting specific programs in place for those working in potentially high-hazard environments.\n\nAvailable Information\nThe Company’s Annual Reports on Form 10-K, Quarterly Reports on Form 10-Q, Current Reports on Form 8-K, and amendments to reports filed pursuant to Sections 13(a) and 15(d) of the Securities Exchange Act of 1934, as amended (“Exchange Act”), are filed with the U.S. Securities and Exchange Commission (“SEC”). Such reports and other information filed by the Company with the SEC are available free of charge at investor.apple.com/investor-relations/sec-filings/default.aspx when such reports are available on the SEC’s website. The Company periodically provides certain information for investors on its corporate website, www.apple.com, and its investor relations website, investor.apple.com. This includes press releases and other information about financial performance, information on corporate governance, and details related to the Company’s annual meeting of shareholders. The information contained on the websites referenced in this Form 10-K is not incorporated by reference into this filing. Further, the Company’s references to website URLs are intended to be inactive textual references only.\nApple Inc. | 2025 Form 10-K | 4"
}
```

The `text` field contains the complete extracted section content. Valid `section_name` values are: `Business`, `Risk Factors`, `Management’s Discussion and Analysis`, `Financial Statements`.

---

## 4. Ask a question — `POST /questions/ask`

The RAG pipeline embeds the query, retrieves the most relevant chunks via vector similarity (pgvector), and synthesizes an answer with inline `[n]` citations using GPT-4o-mini.

- Use `company_filter` to scope to a single company.
- Use `section_filter` to scope to a specific section (e.g., `"Risk Factors"`, `"Business"`).
- Omit both filters for multi-company comparisons — the server automatically does per-company retrieval to ensure balanced representation.

### Q1: What are the top business risks described by the company?

```bash
curl -X POST http://localhost:8000/questions/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the top business risks described by the company?",
    "company_filter": "Apple Inc.",
    "section_filter": "Risk Factors"
  }'
```

Response:

```json
{
    "answer": "The top business risks described by Apple Inc. include:\n\n- **Cybersecurity Risks**: The company faces vulnerabilities to hacking, ransomware attacks, and other malicious activities that can lead to unauthorized access to sensitive information. Despite implementing security measures like multifactor authentication, these may not be sufficient to prevent all incidents [1][4].\n\n- **Investment Risks**: Investments in new business strategies, commercial relationships, and acquisitions may disrupt ongoing operations and present unforeseen risks, potentially adversely affecting the company's business and financial condition [1].\n\n- **Natural Disasters and Climate Change**: Many of the company's operations are in areas prone to natural disasters, which can disrupt manufacturing and delivery, increase costs, and negatively impact consumer demand [3].\n\n- **Macroeconomic Conditions**: Global and regional economic conditions significantly affect the company's performance. Adverse conditions such as recession, inflation, and currency fluctuations can impact consumer confidence and spending [5].\n\n- **Political and Geopolitical Risks**: Political events, trade disputes, and geopolitical tensions can adversely affect the company and its global operations, including supply chain disruptions [5].\n\n- **Supply Chain Risks**: Reliance on single or limited sources for critical components increases vulnerability to business interruptions, which can have significant negative consequences [3].",
    "sources": [
        {
            "chunk_id": "df1dd492-2122-4e7a-b6a4-897ad1f2c334",
            "company": "Apple Inc.",
            "section": "Risk Factors",
            "snippet": "As with all companies, the security the Company has implemented may not be sufficient for all eventualities and are vulnerable to hacking, ransomware attacks, employee error, malfeasance, system error, faulty password management or other irregularities...",
            "score": 0.63776
        },
        {
            "chunk_id": "f34b26f4-3437-4657-92e5-00b639c4d1e4",
            "company": "Apple Inc.",
            "section": "Risk Factors",
            "snippet": "Globally, attacks are expected to continue accelerating in both frequency and sophistication with increasing use by actors of tools and techniques that are designed to circumvent controls, avoid detection...",
            "score": 0.605002
        },
        {
            "chunk_id": "e31f9fbe-bc82-4c7b-919b-e5cecd1338c1",
            "company": "Apple Inc.",
            "section": "Risk Factors",
            "snippet": "Many of the Company's operations, retail stores and facilities, as well as critical business operations of the Company's suppliers and contract manufacturers, are in locations that are prone to earthquakes and other natural disasters...",
            "score": 0.566202
        },
        {
            "chunk_id": "23164f88-2770-4837-8e57-f057c4f53a2f",
            "company": "Apple Inc.",
            "section": "Risk Factors",
            "snippet": "The Company devotes significant resources to systems and data security, including through the use of encryption and other security measures intended to protect its systems and data...",
            "score": 0.566152
        },
        {
            "chunk_id": "281054c2-562d-4609-92eb-404914c8dcff",
            "company": "Apple Inc.",
            "section": "Risk Factors",
            "snippet": "Item 1A. Risk Factors\nThe following summarizes factors that could have a material adverse effect on the Company's business, reputation, results of operations, financial condition and stock price...",
            "score": 0.561248
        }
    ],
    "model_used": "gpt-4o-mini-2024-07-18",
    "retrieval": {
        "top_k": 5,
        "company_filter": "Apple Inc.",
        "section_filter": "Risk Factors",
        "mode": "single"
    }
}
```

### Q2: What does the company say about revenue growth or business performance?

```bash
curl -X POST http://localhost:8000/questions/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What does the company say about revenue growth or business performance?",
    "company_filter": "Apple Inc.",
    "section_filter": "Management'\''s Discussion and Analysis"
  }'
```

Response:

```json
{
    "answer": "- **Overall Revenue Growth**: Apple Inc. reported total net sales of $416,161 million for 2025, which is a 6% increase compared to $391,035 million in 2024 [3].\n\n- **Segment Performance**:\n  - **Americas**: Net sales increased by 7% from $167,045 million in 2024 to $178,353 million in 2025, primarily due to higher net sales of iPhone and Services [3].\n  - **Europe**: Net sales increased by 10% from $101,328 million in 2024 to $111,032 million in 2025, driven by higher net sales of Services, iPhone, and Mac [3].\n  - **Greater China**: Net sales decreased by 4% from $66,952 million in 2024 to $64,377 million in 2025, mainly due to lower net sales of iPhone, partially offset by higher net sales of Mac [3].\n  - **Japan**: Net sales increased by 15% from $25,052 million in 2024 to $28,703 million in 2025, attributed to higher net sales of iPhone, Services, and iPad [3].\n  - **Rest of Asia Pacific**: Net sales increased by 10% from $30,658 million in 2024 to $33,696 million in 2025 [3].\n\n- **Gross Margin**: The total gross margin percentage for Apple was 46.9% in 2025, an increase from 46.2% in 2024, indicating improved profitability [1].\n\n- **Operating Expenses**: Total operating expenses increased by 8% in 2025 compared to 2024, reaching $62,151 million, which reflects ongoing investments in research and development and selling, general, and administrative expenses [1].\n\n- **Macroeconomic Impact**: The company noted that macroeconomic conditions, including inflation and currency fluctuations, have impacted its results and could continue to do so in the future [3].",
    "sources": [
        {
            "chunk_id": "12d3d5f6-d1b7-4350-a38d-92a71e39a8aa",
            "company": "Apple Inc.",
            "section": "Management's Discussion and Analysis",
            "snippet": "Gross margin percentage:\nProducts36.8%37.2%36.5%\nServices75.4%73.9%70.8%\nTotal gross margin percentage46.9%46.2%44.1%\n\nProducts Gross Margin\nProducts gross margin increased during 2025 compared to 2024...",
            "score": 0.48222
        },
        {
            "chunk_id": "ca399fb6-6fcb-42ad-9c25-1a36a7fb0763",
            "company": "Apple Inc.",
            "section": "Management's Discussion and Analysis",
            "snippet": "Capital Return Program\nIn addition to its contractual cash requirements, the Company has an authorized share repurchase program...",
            "score": 0.47501
        },
        {
            "chunk_id": "85f290d7-6ac6-4485-9c13-b1e40217f341",
            "company": "Apple Inc.",
            "section": "Management's Discussion and Analysis",
            "snippet": "Fiscal Period\nThe Company's fiscal year is the 52- or 53-week period that ends on the last Saturday of September...\n\nMacroeconomic Conditions\nMacroeconomic conditions, including inflation, interest rate...",
            "score": 0.456594
        },
        {
            "chunk_id": "0e2836d4-5e92-41a1-a4d2-dc983f680c57",
            "company": "Apple Inc.",
            "section": "Management's Discussion and Analysis",
            "snippet": "Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations...",
            "score": 0.441051
        },
        {
            "chunk_id": "71486111-6bc3-412e-832a-f35a0d4448b0",
            "company": "Apple Inc.",
            "section": "Management's Discussion and Analysis",
            "snippet": "Recent Accounting Pronouncements\nInternal-Use Software...",
            "score": 0.434705
        }
    ],
    "model_used": "gpt-4o-mini-2024-07-18",
    "retrieval": {
        "top_k": 5,
        "company_filter": "Apple Inc.",
        "section_filter": "Management's Discussion and Analysis",
        "mode": "single"
    }
}
```

### Q3: What are the company's main business segments or operating priorities?

```bash
curl -X POST http://localhost:8000/questions/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the company'\''s main business segments or operating priorities?",
    "company_filter": "Apple Inc.",
    "section_filter": "Business"
  }'
```

Response:

```json
{
    "answer": "- **Main Business Segments**: Apple Inc. manages its business primarily on a geographic basis with the following reportable segments:\n  - Americas (North and South America)\n  - Europe (including India, the Middle East, and Africa)\n  - Greater China (China mainland, Hong Kong, and Taiwan)\n  - Japan\n  - Rest of Asia Pacific (Australia, New Zealand, and other Asian countries not included in other segments) [1][2].\n\n- **Operating Priorities**:\n  - Ensuring the timely introduction of innovative new products, services, and technologies [3].\n  - Competing effectively through factors such as price, product and service features, quality, design, and technology innovation [3].\n  - Expanding market opportunities related to smartphones, personal computers, tablets, wearables, accessories, and services [3].\n  - Addressing competition characterized by aggressive pricing and imitation of products [3].\n  - Managing supply chain challenges, including component availability and pricing fluctuations [3].",
    "sources": [
        {
            "chunk_id": "32f9a134-3f48-4444-ac3d-71fb0b36455f",
            "company": "Apple Inc.",
            "section": "Business",
            "snippet": "Segments\nThe Company manages its business primarily on a geographic basis. The Company's reportable segments consist of the Americas, Europe, Greater China, Japan and Rest of Asia Pacific...",
            "score": 0.574336
        },
        {
            "chunk_id": "27fffaf7-e7d3-43ab-ab82-6305219bd0a7",
            "company": "Apple Inc.",
            "section": "Business",
            "snippet": "Item 1. Business\n\nCompany Background\nThe Company designs, manufactures and markets smartphones, personal computers, tablets, wearables and accessories, and sells a variety of related services...",
            "score": 0.57321
        },
        {
            "chunk_id": "829ab26b-532a-46af-b1ed-0bdd413525b8",
            "company": "Apple Inc.",
            "section": "Business",
            "snippet": "The Company's ability to compete successfully depends heavily on ensuring the continuing and timely introduction of innovative new products, services and technologies to the marketplace...",
            "score": 0.487586
        },
        {
            "chunk_id": "74a06b1f-7fcc-437f-8b58-9e9fb0a5fc9c",
            "company": "Apple Inc.",
            "section": "Business",
            "snippet": "Intellectual Property\nThe Company currently holds a broad collection of intellectual property rights relating to certain aspects of its hardware, software and services...",
            "score": 0.479295
        },
        {
            "chunk_id": "a06b2beb-a369-48cc-a4b7-3cf2591c0050",
            "company": "Apple Inc.",
            "section": "Business",
            "snippet": "Business Seasonality and Product Introductions\nThe Company has historically experienced higher net sales in its first quarter compared to other quarters...",
            "score": 0.475758
        }
    ],
    "model_used": "gpt-4o-mini-2024-07-18",
    "retrieval": {
        "top_k": 5,
        "company_filter": "Apple Inc.",
        "section_filter": "Business",
        "mode": "single"
    }
}
```

### Q4: Compare risk factors between two companies

No `company_filter` is set, so the server uses **per-company retrieval** — fetching top-K chunks from each company separately to ensure balanced representation in the comparison.

```bash
curl -X POST http://localhost:8000/questions/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare risk factors between Apple and NVIDIA"
  }'
```

Response:

```json
{
    "answer": "### NVIDIA Corporation Risk Factors\n- **Regulatory Compliance**: Compliance with governmental regulations (e.g., IP ownership, taxes, export controls) could increase costs and adversely impact competitive position and financial results [2].\n- **Export Controls**: Changes in U.S. government export controls may harm competitive position and limit market access, particularly in China and other regions [3].\n- **Environmental Regulations**: Compliance with environmental sustainability regulations has not materially impacted operations, but future changes could pose risks [2].\n- **Supply Chain Risks**: Concentration of supply chain in the Asia-Pacific region may limit alternative manufacturing locations and negatively impact business [3].\n\n### Apple Inc. Risk Factors\n- **Sales and Margin Volatility**: Net sales and gross margins are subject to volatility due to pricing pressures, competition, supply shortages, and changes in product demand [6].\n- **Foreign Exchange Risks**: Fluctuations in foreign exchange rates can adversely affect sales and gross margins, particularly for non-U.S. dollar-denominated sales [6].\n- **Component Supply Risks**: Dependence on single or limited sources for certain components may lead to supply constraints and increased costs [10].\n- **Intellectual Property Risks**: The company relies on a broad collection of intellectual property rights, and future licensing needs may not be met on reasonable terms [10].\n\n### Summary\n- **NVIDIA** faces significant risks related to regulatory compliance, export controls, environmental regulations, and supply chain concentration.\n- **Apple** contends with risks from sales volatility, foreign exchange fluctuations, component supply constraints, and intellectual property management.",
    "sources": [
        {
            "chunk_id": "a33bc0b0-9b9f-45a5-94d7-e00f81282c29",
            "company": "NVIDIA Corporation",
            "section": "Business",
            "snippet": "...hold advanced degrees. Additionally, we have increased our focus on diversity recruiting...",
            "score": 0.466956
        },
        {
            "chunk_id": "ad2459dc-d1ee-4e41-8f4a-4e14727ece34",
            "company": "NVIDIA Corporation",
            "section": "Business",
            "snippet": "Compliance with existing or future governmental regulations, including, but not limited to, those pertaining to IP ownership and infringement, taxes, import and export requirements...",
            "score": 0.462594
        },
        {
            "chunk_id": "c083887a-9d74-4fda-9c6d-0f477cd1e2d8",
            "company": "NVIDIA Corporation",
            "section": "Business",
            "snippet": "After a 120-day delayed compliance period, the IFR will, unless modified, impose a worldwide licensing requirement on all products classified under Export Control Classification Numbers...",
            "score": 0.457952
        },
        {
            "chunk_id": "c5535d18-b686-4c76-9461-114d722f7dc9",
            "company": "NVIDIA Corporation",
            "section": "Management's Discussion and Analysis",
            "snippet": "Item 7.\n\nManagement's Discussion and Analysis of Financial Condition and Results of Operations...",
            "score": 0.455868
        },
        {
            "chunk_id": "0082d5d2-0281-4872-90ef-c3ac7d38f6fd",
            "company": "NVIDIA Corporation",
            "section": "Business",
            "snippet": "Our workforce is 82% technical and 51%...",
            "score": 0.454181
        },
        {
            "chunk_id": "a90078a5-106f-4aa2-88c8-ad71d2447c47",
            "company": "Apple Inc.",
            "section": "Risk Factors",
            "snippet": "Financial Risks\nThe Company's net sales and gross margins are subject to volatility and downward pressure due to a variety of factors...",
            "score": 0.412582
        },
        {
            "chunk_id": "07137c88-d6cd-4fae-aff7-fbb47f0cc8d4",
            "company": "Apple Inc.",
            "section": "Financial Statements",
            "snippet": "202520242023\nNet sales:\nU.S.$151,790 $142,196 $138,573\nChina (1)\n64,377 66,952 72,559...",
            "score": 0.40587
        },
        {
            "chunk_id": "7c8bda65-fb1c-45aa-a78e-80959b2658e4",
            "company": "Apple Inc.",
            "section": "Financial Statements",
            "snippet": "2024\nAmericasEuropeGreater\nChina\nJapanRest of\nAsia PacificCorporateTotal\nNet sales$167,045 $101,328 $66,952 $25,052 $30,658...",
            "score": 0.404184
        },
        {
            "chunk_id": "32f9a134-3f48-4444-ac3d-71fb0b36455f",
            "company": "Apple Inc.",
            "section": "Business",
            "snippet": "Segments\nThe Company manages its business primarily on a geographic basis...",
            "score": 0.403084
        },
        {
            "chunk_id": "b78b312d-4b81-4eff-991b-0237abec4b21",
            "company": "Apple Inc.",
            "section": "Business",
            "snippet": "Supply of Components\nAlthough most components essential to the Company's business are generally available from multiple sources, certain components are currently obtained from single or limited sources...",
            "score": 0.401831
        }
    ],
    "model_used": "gpt-4o-mini-2024-07-18",
    "retrieval": {
        "top_k": 5,
        "company_filter": null,
        "section_filter": null,
        "mode": "per_company"
    }
}
```

### Q5: What themes appear repeatedly in management discussion?

```bash
curl -X POST http://localhost:8000/questions/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What themes appear repeatedly in management discussion?",
    "company_filter": "Apple Inc.",
    "section_filter": "Management'\''s Discussion and Analysis"
  }'
```

Response:

```json
{
    "answer": "The following themes appear repeatedly in the management discussion for Apple Inc.:\n\n- **Judgment and Estimates**: Management emphasizes the need for significant judgment in preparing financial statements, particularly regarding uncertain tax positions and legal contingencies, which can materially impact financial results [1].\n\n- **Macroeconomic Conditions**: The impact of macroeconomic factors such as inflation, interest rates, and currency fluctuations is highlighted as having a direct and indirect effect on the company's financial condition and operating results [2][5].\n\n- **Legal and Regulatory Risks**: The discussion includes the uncertainties associated with legal proceedings and tax positions, indicating that outcomes may differ from management's expectations, potentially affecting financial results [1].\n\n- **Product Announcements**: The company frequently discusses new product, service, and software announcements throughout the fiscal year, indicating a focus on innovation and market responsiveness [2].\n\n- **Capital Return Program**: There is a consistent mention of the company's share repurchase program and dividend policy, reflecting a commitment to returning value to shareholders [4].\n\n- **Impact of Tariffs**: The potential adverse effects of U.S. tariffs and international trade measures on the company's operations and financial performance are noted, indicating a concern for external economic factors [5].",
    "sources": [
        {
            "chunk_id": "5d700e41-877e-4bdc-8e22-7a86acee82d0",
            "company": "Apple Inc.",
            "section": "Management's Discussion and Analysis",
            "snippet": "Critical Accounting Estimates\nThe preparation of financial statements and related disclosures in conformity with U.S. generally accepted accounting principles...",
            "score": 0.333044
        },
        {
            "chunk_id": "0e2836d4-5e92-41a1-a4d2-dc983f680c57",
            "company": "Apple Inc.",
            "section": "Management's Discussion and Analysis",
            "snippet": "Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations...",
            "score": 0.314547
        },
        {
            "chunk_id": "71486111-6bc3-412e-832a-f35a0d4448b0",
            "company": "Apple Inc.",
            "section": "Management's Discussion and Analysis",
            "snippet": "Recent Accounting Pronouncements\nInternal-Use Software...",
            "score": 0.285113
        },
        {
            "chunk_id": "ca399fb6-6fcb-42ad-9c25-1a36a7fb0763",
            "company": "Apple Inc.",
            "section": "Management's Discussion and Analysis",
            "snippet": "Capital Return Program\nIn addition to its contractual cash requirements, the Company has an authorized share repurchase program...",
            "score": 0.280177
        },
        {
            "chunk_id": "85f290d7-6ac6-4485-9c13-b1e40217f341",
            "company": "Apple Inc.",
            "section": "Management's Discussion and Analysis",
            "snippet": "Fiscal Period\nThe Company's fiscal year is the 52- or 53-week period that ends on the last Saturday of September...\n\nMacroeconomic Conditions\nMacroeconomic conditions, including inflation, interest rate...",
            "score": 0.264814
        }
    ],
    "model_used": "gpt-4o-mini-2024-07-18",
    "retrieval": {
        "top_k": 5,
        "company_filter": "Apple Inc.",
        "section_filter": "Management's Discussion and Analysis",
        "mode": "single"
    }
}
```

---

## 5. Submit an async analysis job — `POST /analysis-jobs`

Analysis jobs run asynchronously. The endpoint returns HTTP 202 with a job ID and `status: "queued"`. Supported job kinds: `ingest`, `ask`, and `compare`.

### Compare topic across companies

```bash
curl -X POST http://localhost:8000/analysis-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "compare",
    "payload": {
      "topic": "supply chain concentration risk",
      "companies": ["Apple Inc.", "NVIDIA Corporation"]
    }
  }'
```

Response (HTTP 202 Accepted):

```json
{
    "id": "dd07996c-0231-461f-a3be-cd92b9dfe996",
    "kind": "compare",
    "status": "queued",
    "payload": {
        "topic": "supply chain concentration risk",
        "companies": [
            "Apple Inc.",
            "NVIDIA Corporation"
        ]
    },
    "result": null,
    "error": null,
    "created_at": "2026-05-01T17:27:07.623916Z",
    "started_at": null,
    "finished_at": null
}
```

### Ingest as a job

```bash
curl -X POST http://localhost:8000/analysis-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "ingest",
    "payload": {
      "url": "https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm",
      "company": "Microsoft Corporation",
      "ticker": "MSFT",
      "fiscal_year": 2025
    }
  }'
```

---

## 6. Poll a job — `GET /analysis-jobs/{id}`

Poll until `status` reaches `"done"` or `"error"`. The `result` field is populated on completion.

```bash
curl http://localhost:8000/analysis-jobs/dd07996c-0231-461f-a3be-cd92b9dfe996
```

Response (completed):

```json
{
    "id": "dd07996c-0231-461f-a3be-cd92b9dfe996",
    "kind": "compare",
    "status": "done",
    "payload": {
        "topic": "supply chain concentration risk",
        "companies": [
            "Apple Inc.",
            "NVIDIA Corporation"
        ]
    },
    "result": {
        "topic": "supply chain concentration risk",
        "by_company": {
            "Apple Inc.": {
                "answer": "Apple Inc. identifies several key points regarding supply chain concentration risk:\n\n- **Dependence on Single or Limited Sources**: The company obtains certain components from single or limited sources, which exposes it to significant supply and pricing risks. This includes custom components that are not commonly used by competitors, leading to potential shortages and price increases [1][2][4].\n\n- **Impact of Industry-Wide Shortages**: Many components, even those available from multiple sources, can be subject to industry-wide shortages and significant commodity pricing fluctuations, adversely affecting the company's business and financial condition [2][3].\n\n- **Risks from Outsourcing**: A significant majority of Apple's manufacturing is performed by outsourcing partners located primarily in Asia. This reliance on external partners can diminish the company's control over production and distribution, potentially affecting cost, quality, and availability of products [1][3].\n\n- **Challenges in Supply Chain Management**: Changes or additions to the supply chain require considerable time and resources and involve significant risks, including exposure to regulatory and operational challenges [1][4].\n\n- **Geopolitical and Trade Risks**: Restrictions on international trade, such as tariffs, can materially affect the company's supply chain and operations [3][5].",
                "sources": [
                    { "section": "Risk Factors", "snippet": "Success also relies on the Company's ability to manage the risks associated with new technologies and production ramp-up issues...", "score": 0.478311 },
                    { "section": "Financial Statements", "snippet": "Note 12 – Commitments, Contingencies and Supply Concentrations...", "score": 0.453422 },
                    { "section": "Risk Factors", "snippet": "The Company has a large, global business with sales outside the U.S. representing a majority of the Company's total net sales...", "score": 0.447815 },
                    { "section": "Risk Factors", "snippet": "Additionally, the Company's new products often utilize custom components available from only one source...", "score": 0.415881 },
                    { "section": "Risk Factors", "snippet": "Item 1A. Risk Factors...", "score": 0.409693 }
                ]
            },
            "NVIDIA Corporation": {
                "answer": "NVIDIA Corporation highlights several aspects of supply chain concentration risk:\n\n- **Dependency on Third-Party Suppliers**: NVIDIA relies on foundries and subcontractors for manufacturing, assembly, testing, and packaging, which reduces their control over product quantity, quality, and delivery schedules [5].\n\n- **Geographic Concentration**: A significant portion of NVIDIA's operations and suppliers are located in specific regions, particularly in Asia. This concentration makes their operations vulnerable to disruptions from natural disasters, geopolitical tensions, and other adverse events [4].\n\n- **Limited Number of Suppliers**: The company faces risks due to the limited number and geographic concentration of global suppliers, foundries, and contract manufacturers [5].\n\n- **Integration Complexity**: As NVIDIA integrates new suppliers and contract manufacturers into their supply chain, the complexity of managing multiple suppliers increases [5].",
                "sources": [
                    { "section": "Business", "snippet": "For example, our ability to sell certain products has been and could be impeded if components necessary for the finished products are not available from third parties...", "score": 0.438152 },
                    { "section": "Business", "snippet": "Competition could adversely impact our market share and financial results...", "score": 0.43783 },
                    { "section": "Business", "snippet": "In general, if a product liability claim regarding any of our products is brought against us...", "score": 0.426929 },
                    { "section": "Business", "snippet": "Our corporate headquarters, a large portion of our current data center capacity, and a portion of our research and development activities are located in California...", "score": 0.423238 },
                    { "section": "Business", "snippet": "cryptocurrency mining, on demand for our products...", "score": 0.42272 }
                ]
            }
        }
    },
    "error": null,
    "created_at": "2026-05-01T17:27:07.623916Z",
    "started_at": "2026-05-01T17:27:07.640821Z",
    "finished_at": "2026-05-01T17:27:18.848030Z"
}
```

---

## Quick reference — mapping questions to API calls

| Question | Endpoint | Filters |
|---|---|---|
| What are the top business risks described by the company? | `POST /questions/ask` | `company_filter` + `section_filter: "Risk Factors"` |
| What does the company say about revenue growth or business performance? | `POST /questions/ask` | `company_filter` + `section_filter: "Management's Discussion and Analysis"` |
| What are the company's main business segments or operating priorities? | `POST /questions/ask` | `company_filter` + `section_filter: "Business"` |
| Compare risk factors between two companies | `POST /questions/ask` | No filters (triggers per-company retrieval) |
| What themes appear repeatedly in management discussion? | `POST /questions/ask` | `company_filter` + `section_filter: "Management's Discussion and Analysis"` |
