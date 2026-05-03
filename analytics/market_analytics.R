# AgroSense Market Analytics
# Statistical analysis of crop price trends

library(ggplot2)
library(dplyr)

args       <- commandArgs(trailingOnly=TRUE)
csv_path   <- ifelse(length(args)>0, args[1], "analytics/price_history.csv")
output_dir <- ifelse(length(args)>1, args[2], "static/charts")
dir.create(output_dir, showWarnings=FALSE, recursive=TRUE)

data       <- read.csv(csv_path, stringsAsFactors=FALSE)
data$date  <- as.Date(data$date)
data$price <- as.numeric(data$price)

cat("Loaded", nrow(data), "price records\n")

# ── Theme ──────────────────────────────────────────────
theme_agro <- theme_minimal() +
  theme(
    plot.background  = element_rect(fill="#ffffff", color=NA),
    panel.background = element_rect(fill="#f0f7f0", color=NA),
    panel.grid.major = element_line(color="#c8e6c9"),
    panel.grid.minor = element_blank(),
    plot.title       = element_text(color="#1b5e20", size=14, face="bold"),
    plot.subtitle    = element_text(color="#388e3c", size=10),
    axis.title       = element_text(color="#2e7d32", size=10),
    axis.text        = element_text(color="#333333", size=9),
    legend.title     = element_text(color="#2e7d32"),
  )

colors <- c("Tomato"="#e53935","Rice"="#fb8c00","Wheat"="#fdd835",
            "Onion"="#8e24aa","Potato"="#1e88e5")

# ── Chart 1: Price Trend ───────────────────────────────
cat("Generating price trend chart...\n")
p1 <- ggplot(data, aes(x=date, y=price, color=crop, group=crop)) +
  geom_line(size=1.2, alpha=0.9) +
  geom_point(size=1.5, alpha=0.7) +
  scale_color_manual(values=colors) +
  scale_y_continuous(labels=function(x) paste0("Rs.", x)) +
  labs(
    title    = "Crop Price Trends (Last 30 Days)",
    subtitle = "Price per quintal in Indian Rupees",
    x        = "Date", y = "Price (Rs/quintal)",
    color    = "Crop"
  ) +
  theme_agro
ggsave(file.path(output_dir, "price_trend.png"),
       p1, width=8, height=4, dpi=120, bg="white")

# ── Chart 2: Price Distribution ────────────────────────
cat("Generating price distribution chart...\n")
p2 <- ggplot(data, aes(x=crop, y=price, fill=crop)) +
  geom_boxplot(alpha=0.8, outlier.color="#e53935") +
  geom_jitter(width=0.2, alpha=0.3, size=1) +
  scale_fill_manual(values=colors) +
  scale_y_continuous(labels=function(x) paste0("Rs.", x)) +
  labs(
    title    = "Price Volatility by Crop",
    subtitle = "Box plot showing price spread over 30 days",
    x        = "Crop", y = "Price (Rs/quintal)"
  ) +
  theme_agro +
  theme(legend.position="none")
ggsave(file.path(output_dir, "price_volatility.png"),
       p2, width=8, height=4, dpi=120, bg="white")

# ── Chart 3: Profit Comparison ─────────────────────────
cat("Generating profit comparison chart...\n")
yield_per_acre <- c(Tomato=12000, Rice=2000, Wheat=1800, Onion=8000, Potato=10000)
cost_per_acre  <- 25000

profit_data <- data %>%
  group_by(crop) %>%
  summarise(avg_price=mean(price), .groups="drop") %>%
  mutate(
    yield_kg   = yield_per_acre[crop],
    revenue    = (yield_kg / 100) * avg_price,
    profit     = revenue - cost_per_acre,
    profitable = profit > 0
  )

p3 <- ggplot(profit_data, aes(x=reorder(crop,-profit),
                               y=profit/1000, fill=profitable)) +
  geom_col(alpha=0.85, width=0.6) +
  geom_hline(yintercept=0, color="#e53935", linetype="dashed") +
  scale_fill_manual(values=c("TRUE"="#2e7d32","FALSE"="#e53935")) +
  scale_y_continuous(labels=function(x) paste0("Rs.", x, "K")) +
  labs(
    title    = "Expected Profit per Acre by Crop",
    subtitle = "Based on average market price × yield − farming cost",
    x        = "Crop", y = "Profit (Rs. thousands/acre)"
  ) +
  theme_agro +
  theme(legend.position="none")
ggsave(file.path(output_dir, "profit_comparison.png"),
       p3, width=8, height=4, dpi=120, bg="white")

# ── Chart 4: Weekly Average ────────────────────────────
cat("Generating weekly average chart...\n")
data$week <- format(data$date, "%b %d")
weekly    <- data %>%
  group_by(crop, week) %>%
  summarise(avg_price=mean(price), .groups="drop")

p4 <- ggplot(weekly, aes(x=week, y=avg_price, fill=crop)) +
  geom_col(position="dodge", alpha=0.85) +
  scale_fill_manual(values=colors) +
  scale_y_continuous(labels=function(x) paste0("Rs.", x)) +
  labs(
    title    = "Weekly Average Crop Prices",
    subtitle = "Grouped bar chart — price comparison across weeks",
    x        = "Week", y = "Avg Price (Rs/quintal)",
    fill     = "Crop"
  ) +
  theme_agro +
  theme(axis.text.x=element_text(angle=45, hjust=1, size=7))
ggsave(file.path(output_dir, "weekly_avg.png"),
       p4, width=8, height=4, dpi=120, bg="white")

cat("All charts saved to:", output_dir, "\n")