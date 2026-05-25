-- Create products table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL,
    product_id VARCHAR(100) NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    image TEXT,
    current_price DECIMAL(12, 2),
    lowest_price DECIMAL(12, 2),
    highest_price DECIMAL(12, 2),
    currency VARCHAR(10) DEFAULT 'INR',
    last_checked TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, product_id)
);

-- Create tracked_items table
CREATE TABLE IF NOT EXISTS tracked_items (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    target_price DECIMAL(12, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, product_id)
);

-- Create price_history table
CREATE TABLE IF NOT EXISTS price_history (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    price DECIMAL(12, 2) NOT NULL,
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_products_platform_pid ON products(platform, product_id);
CREATE INDEX IF NOT EXISTS idx_tracked_items_user ON tracked_items(user_id);
CREATE INDEX IF NOT EXISTS idx_price_history_product ON price_history(product_id);
