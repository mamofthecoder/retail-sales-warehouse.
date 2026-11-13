CREATE TABLE dim_date
(
    date_key integer NOT NULL,
    full_date date NOT NULL,
    year integer NOT NULL,
    month_number integer NOT NULL,
    CONSTRAINT dim_date_pkey PRIMARY KEY (date_key),
    CONSTRAINT dim_date_full_date_key UNIQUE (full_date),
    CONSTRAINT dim_date_month_number_check CHECK (month_number >= 1 AND month_number <= 12)
);

CREATE TABLE dim_product
(
    product_id integer NOT NULL,
    product_name text COLLATE pg_catalog."default" NOT NULL,
    product_category text COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT dim_product_pkey PRIMARY KEY (product_id)
);

CREATE TABLE fact_sales
(
    order_item_id integer NOT NULL,
    order_id integer NOT NULL,
    order_date_key integer NOT NULL,
    product_id integer NOT NULL,
    quantity integer NOT NULL,
    line_revenue numeric(12,2) NOT NULL,
    CONSTRAINT fact_sales_pkey PRIMARY KEY (order_item_id),
    CONSTRAINT fact_sales_order_date_key_fkey FOREIGN KEY (order_date_key)
        REFERENCES dim_date (date_key) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION,
    CONSTRAINT fact_sales_product_id_fkey FOREIGN KEY (product_id)
        REFERENCES dim_product (product_id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION,
    CONSTRAINT fact_sales_quantity_check CHECK (quantity > 0),
    CONSTRAINT fact_sales_line_revenue_check CHECK (line_revenue >= 0::numeric)
);

CREATE TABLE sales_load_rejections
(
    batch_id integer NOT NULL,
    order_item_id integer NOT NULL,
    rejection_reason text COLLATE pg_catalog."default" NOT NULL,
    rejected_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at timestamp with time zone,
    CONSTRAINT sales_load_rejections_pkey PRIMARY KEY (batch_id, order_item_id)
);

CREATE TABLE stg_sales
(
    batch_id integer NOT NULL,
    order_item_id integer NOT NULL,
    order_id integer,
    product_id integer,
    quantity integer,
    sale_date date,
    line_revenue numeric(12,2),
    CONSTRAINT stg_sales_pkey PRIMARY KEY (batch_id, order_item_id)
);

