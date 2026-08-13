Here is the complete compilation of your industrial attachment logbook entries already written from Week 1 to Week 7:
## WEEK 1 (25th May 2026 – 29th May 2026)

* Monday – Wednesday: (Blank in logbook)
* Thursday: Reported to Techbiz for my first day of industrial attachment and met my supervisor, Kelvin. I was introduced to engineering team and Kelvin took me through the company's daily development workflow guidelines and operational rules.
* Friday: Devoted the day to configuring my local development machine under Kelvin's supervision. I installed Node.js, PHP, Composer, and Git to my machine.

------------------------------
## WEEK 2 (1st June 2026 – 5th June 2026)

* Monday: Public Holiday
* Tuesday: Began intensive training on Next.js structures, focusing heavily on the App Router architecture. Kelvin explained the functional differences between Server Components and Client Components for performance optimization. I practiced creating nested page layouts and styling using Tailwind CSS utility patterns.
* Wednesday: Shifted focus onto foundational React concepts, practicing components and data passing. I set up several forms to learn standard data binding using functional hooks.
* Thursday: Explored UI design by working directly with shadcn/ui components. I configured the component's Tailwind CSS classes to establish clean interface. I created dialog containers, custom form dropdown and popover components to learn layout constraints.
* Friday: Studied client-side authentication and routing protection using middleware intercepts. I configured mock tokens within the application context to test user redirect logic across restricted pages. Kelvin reviewed my local tests providing feedback on optimizing my data handling mechanisms.

------------------------------
## WEEK 3 (8th June 2026 – 12th June 2026)

* Monday: Started my first active production project: the Ocean Motors Car Dealership Platform. I planned the comprehensive application folder layout and initialized Next.js project cardealer using npm to scaffold the project structure with Next.js App Router conventions.
* Tuesday: Focused on rapid prototyping and designing the user interface screens using Google v0 to achieve fast visual mockups. I translated these design layouts directly into frontend structures using Tailwind CSS. I established the foundational vehicle display grid blocks to cleanly host future dynamic automotive listings.
* Wednesday: Worked directly with backend database configurations by initializing Supabase database dashboard. Also worked on building the core landing page components and implementing yesterday's vehicle display grids. I connected UI elements using supabase data and also learned how to setup cloudinary to host car images.
* Thursday: I worked on implementing vehicle detail view component pages. I mapped out dynamic route handling logic so that selecting a vehicle card displays complete technical details and pricing.
* Friday: Today (Incomplete entry)

------------------------------
## WEEK 4 (15th June 2026 – 19th June 2026)

* Monday: Dedicated the day to refining the ocean motors platform. I updated the state logic to allow customers to filter cars by condition types, such as Local Used, Brand New and debugging. Also designed and built the admin dashboard for vehicle inventory listing, and leads page under /admin path. I gave every vehicle a unique stock code and clean slug so each car gets its own shareable link.
* Tuesday: Today I focused on writing the full add new vehicles form used by administrators. I added Cloudinary-backed image upload fields and validation that flags missing or invalid entries before saving.
* Wednesday: Added lead generation feature to platform by configuring a floating Whatsapp action components on the homepage and vehicle details page. I refined the button's visibility and swapped the generic icon for the official WhatsApp icon.
* Thursday: Today I performed deep end-to-end user testing across vercel builds. I walked the flows on desktop and mobile and noted the responsive layout issues to fix before launch.
* Friday: Began pushing for production and handover of the platform. I assisted in purchasing and provisioning the domain name via Name.com. I used cloudflares nameservers and entered Vercel's target record to cloudflare DNS dashboard. Also added domain name to google search console for indexing. I also made the site fall back to demo inventory when external services are unavailable.

------------------------------
## WEEK 5 (22nd June 2026 – 26th June 2026)

* Monday: Transitioned to my second project a hardware store platform. Reviewed the project scope with Kelvin and other engineers. I used google stitch to rapidly build and structure user interface wireframes. I planned to use same stack as previous project: Next.js, Supabase Cloudinary for images and videos.
* Tuesday: Focused entirely on translating stitch mockups into functional Next.js components for the homepage. I linked the homepages category section to category page and its products. I set up supabase and cloudinary and started database design schema. Created a product and category new and update form to test.
* Wednesday: Engineered a dynamic quotation request feature. Also added whatsapp integration learned during my first project.
* Thursday: Worked on the admin dashboard, added KPI metrics for dashboard, product listings, and its CREATE/UPDATE forms, category listing and forms, quote listing and media for cloudinary management. I integrated the jspdf to generate quotations pdf based on quote request.
* Friday: Worked on full project compilation and live production deployment handover. Kelvin helped me run final project audits, configured production environment variables, deployed to vercel and ran tests to confirm platform operates seamlessly before project sign-off.

------------------------------
## WEEK 6 (29th June 2026 – 3rd July 2026)

* Monday: Started on a Point of Sale Project. Planned the project
* Tuesday: Set up backend postgres database connection in Laravel. Created database migration files for core tables including products, categories, stock levels and user roles. Discussed the database relationship with my supervisor Kelvin, to ensure product prices and tax rates are handled correctly.
* Wednesday: Built the initial Laravel API routes and controller logic for managing products and categories. Implemented basic CRUD operations, allowing system to save and retrieve products details from database. Tested endpoints using Postman to verify server responses.
* Thursday: Worked on the backend logic for processing cart transactions and orders. Created a dedicated sales controller and kept it thin by following CRUDdy by design concept.
* Friday: Implemented the backend logic for shift and physical register management. Created models and migration tables to track open cash registers, starting float amounts and cashier sign-in times.

------------------------------
## WEEK 7 (6th July 2026 – 10th July 2026)

* Monday: Started frontend for the POS project. I set up the Next.js App router layout with sidebar component using shadcn UI. Built the dashboard page that shows summary cards for today's sales, total customers and low-stock items.
* Tuesday: Built the checkout terminal page. Created a searchable grid of products display in the page. Also implemented product search with debounced input.
* Wednesday: Worked on the customer and product management pages. Implemented logic that automatically reduces product inventory quantities whenever a POS sale is completed.
* Thursday: Focused on the checkout flow and receipt generation. Built the payment modal that lets the cashier choose between cash, mpesa or card.
* Friday: Polished the frontend UI to have consistent typography and base colour system.

------------------------------
## WEEK 8 (13th July 2026 – 17th July 2026)

* Monday: Set up the API client on Next.js using fetch to connect to the Laravel backend. Configured authorization headers to save and send user session tokens, allowing only signed-in cashiers to access the POS terminal.
* Tuesday: Connected the checkout terminal to pull live product and category data from the Laravel API. Integrated the search logic to query the backend database directly and return search results dynamically.
* Wednesday: Connected the checkout cart submission flow to the backend sales API. Handled calculations like subtotals, tax rates, and discounts on the backend side, and configured the client to display the final payment summary.
* Thursday: Built the frontend integration for cash register shifts. Configured forms to let cashiers open shifts with a starting cash float, track active registers, and send shift logs back to the Laravel database.
* Friday: Spent the day resolving connection and data mapping bugs. Fixed a CORS error blocking API requests between the frontend and backend, and resolved a client-side state issue where the checkout cart would not empty after a transaction completed.

------------------------------
## WEEK 9 (20th July 2026 – 24th July 2026)

* Monday: Added proper error messages and page validation. Setup custom toast alerts to show backend validation failures, like when product inventory runs out or database transactions fail, without breaking the application.
* Tuesday: Worked on the printer layout styles for customer receipts. Configured CSS media print rules to format the receipt modal cleanly on standard thermal paper rolls and tested default browser print shortcuts.
* Wednesday: Ran full end-to-end checkout cycles with my supervisor Kelvin. We walked through opening a shift, adding items to the cart, processing cash and mobile payments, checking that Postgres stock counts updated correctly, and closing the shift register.
* Thursday: Configured staging environment files and variables to prepare the app for deployment. Tested the production build steps locally for both Laravel and Next.js to make sure all environment flags worked correctly.
* Friday: Completed the system handover with Kelvin. Documented the API route maps, database schema relationships, and local deployment steps, and demonstrated the final application flow to manager.

------------------------------
## WEEK 10 (27th July 2026 – 31st July 2026)

* Monday: Started work on the new KRA tax reconciliation project, which we're calling "Ushuru Lens". I sat down with Umar (our PM) and Kelvin (my supervisor) to get a clear picture of how KRA tax returns need to match our internal SAP ledgers. The main headache is dealing with inconsistent vendor names and different tax category mappings. Since the core value is in the matching logic, I started with the backend: I set up the FastAPI Python backend and began designing the basic database tables.
* Tuesday: Wrote the core reconciliation matching engine in Python (`reconciliation_service.py`). I structured the logic into a 7-stage pipeline (preprocessing, pairing by CU number, validation, tax checks, etc.). To handle typos and abbreviations in vendor names (like "Techbiz Limited" vs "Techbiz Ltd"), I used Python's `difflib.SequenceMatcher` with a similarity threshold of 0.85.
* Wednesday: Tested the backend and reconciliation engine against the SAP Business One test database and dummy KRA data. I connected to the SAP Service Layer to pull test invoices and ran the engine against sample KRA exports to verify it matches records correctly. Hillary, our senior SAP consultant, walked me through the SAP Business One Service Layer invoice endpoints, helped me map how internal database records match up with KRA fields, and helped calibrate the similarity threshold against the test data.
* Thursday: Built the frontend dashboard interface for Ushuru Lens. I initialized a new Next.js project inside the `frontend` folder using the App Router, TypeScript, and Tailwind, and used shadcn/ui to build a simple layout: an upload zone for files, cards for matching stats, and a data table to view the mismatches. I then connected the frontend to the FastAPI backend endpoints using fetch.
* Friday: Got a basic local prototype working end-to-end: upload the Excel template and see the matching results against the SAP test invoices. I ran a quick demo for Umar, Kelvin, and Hillary. They liked the logic but Umar asked me to prepare a formal demo for the wider Infotech team on Monday.

------------------------------
## WEEK 11 (3rd August 2026 – 7th August 2026)

* Monday: Presented the Ushuru Lens prototype to the InfoTech management and developer team. The feedback was very clear: they hated the manual Excel template. They requested direct, automatic parsing of raw KRA CSV exports instead of forcing users to copy-paste data, since that's slow and prone to errors.
* Tuesday: Worked on implementing the CSV parsing feedback. I wrote the parser in `app/services/kra_service.py`. The backend now reads the raw CSV, validates the filename for a KRA section prefix (like `SEC_B`), and dynamically maps columns and VAT rates based on the section profile. I also updated the Next.js frontend upload to take raw CSV files directly.
* Wednesday: Containerized the entire app. I wrote a multi-stage Dockerfile to build Next.js into static files and package the FastAPI backend. I set up Nginx inside the container to serve the frontend on port 8000 and proxy API requests to port 8001. I also created a `docker-compose.yml` to link the application with a PostgreSQL database container.
* Thursday: Spent the day testing the Docker setup locally. I ran into an Nginx issue where static assets under `_next/` were returning 404 errors. I fixed this by adjusting the alias path in `nginx.conf`. I also verified that database migrations run automatically on container startup using `docker-entrypoint.sh`.
* Friday: Deployed the dockerized application to the DigitalOcean droplet. Kelvin helped me set up the server environment, configure the production `.env` variables, and pull the Docker images. We ran the containers and tested the live system with actual raw KRA files, and confirmed it matches records correctly.

-----------------------------
## WEEK 12 (10th August 2026 – 14th August 2026)

* Friday: Returned to the Ocean Motors dealership platform to polish it before it gets showcased to management. I reworked the homepage hero into a cleaner static car presentation, stripping out the heavy framing and auto-rotating animations that made it feel cluttered, and iterated on several design variations before settling on the final layout. I also refined the mobile vehicle details flow so the gallery, specifications, and enquiry call-to-action are easier to reach on a phone, and compacted the admin inventory into a tighter operational workspace for faster stock management. I closed the day by running Lighthouse audits against the production build and comparing the before and after scores with Kelvin to confirm the changes actually improved the page.-

