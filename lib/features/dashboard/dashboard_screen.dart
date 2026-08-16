import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:trademind_ai/features/news/news_screen.dart';
import 'package:trademind_ai/features/scanner/scanner_screen.dart';
import 'package:trademind_ai/features/signals/signals_screen.dart';
import 'package:trademind_ai/models/market_candle.dart';
import 'package:trademind_ai/models/market_overview.dart';
import 'package:trademind_ai/services/trademind_api_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final TrademindApiService _apiService = TrademindApiService();
  late Future<List<MarketSummaryItem>> _marketFuture;
  late Future<MarketOverview?> _overviewFuture;

  @override
  void initState() {
    super.initState();
    _marketFuture = _apiService.getMarketSummary();
    _overviewFuture = _apiService.getMarketOverview();
  }

  Future<void> _reload() async {
    setState(() {
      _marketFuture = _apiService.getMarketSummary();
      _overviewFuture = _apiService.getMarketOverview();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment.topCenter,
            radius: 1.35,
            colors: [Color(0xFF172033), Color(0xFF0A0D14), Color(0xFF070A10)],
          ),
        ),
        child: RefreshIndicator(
          onRefresh: _reload,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'TradeMind Overview',
                          style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Live market pulse, signal shortcuts, and realtime headlines in one place.',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  IconButton.filledTonal(
                    onPressed: _reload,
                    icon: const Icon(Icons.refresh),
                    tooltip: 'Refresh',
                  ),
                ],
              ),
              const SizedBox(height: 16),
              FutureBuilder<MarketOverview?>(
                future: _overviewFuture,
                builder: (context, overviewSnapshot) {
                  if (overviewSnapshot.connectionState == ConnectionState.waiting) {
                    return const Card(
                      child: Padding(
                        padding: EdgeInsets.all(16),
                        child: LinearProgressIndicator(minHeight: 2),
                      ),
                    );
                  }
                  if (overviewSnapshot.hasError) {
                    return const SizedBox.shrink();
                  }
                  final overview = overviewSnapshot.data;
                  if (overview == null) return const SizedBox.shrink();
                  return Card(
                    child: Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            Theme.of(context).colorScheme.primary.withValues(alpha: 0.16),
                            Theme.of(context).colorScheme.surface.withValues(alpha: 0.92),
                          ],
                        ),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Market Pulse',
                            style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                          ),
                          const SizedBox(height: 12),
                          Wrap(
                            spacing: 12,
                            runSpacing: 12,
                            children: [
                              _StatTile(label: 'BTC Price', value: '\$${overview.btcPrice.toStringAsFixed(0)}'),
                              _StatTile(label: 'ETH Price', value: '\$${overview.ethPrice.toStringAsFixed(0)}'),
                              _StatTile(
                                label: 'Fear & Greed',
                                value: overview.fearGreedIndex.toString(),
                                sub: overview.fearGreedClassification,
                              ),
                              _StatTile(
                                label: 'BTC Dominance',
                                value: '${overview.btcDominance.toStringAsFixed(1)}%',
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  'Market Cap: \$${(overview.marketCap / 1e9).toStringAsFixed(1)}B',
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              ),
                              Text(
                                'Updated ${DateFormat('h:mm a').format(overview.updatedAt)}',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 18),
              Text(
                'Quick Access',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 12),
              GridView.count(
                crossAxisCount: MediaQuery.of(context).size.width > 700 ? 3 : 2,
                shrinkWrap: true,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                physics: const NeverScrollableScrollPhysics(),
                childAspectRatio: 1.12,
                children: [
                  _ActionCard(
                    title: 'Scanner',
                    subtitle: 'Multi-timeframe setup scan',
                    icon: Icons.tune,
                    onTap: () {
                      Navigator.of(context).push(
                        MaterialPageRoute(builder: (_) => const ScannerScreen()),
                      );
                    },
                  ),
                  _ActionCard(
                    title: 'Signals',
                    subtitle: 'Active and closed trade calls',
                    icon: Icons.campaign,
                    onTap: () {
                      Navigator.of(context).push(
                        MaterialPageRoute(builder: (_) => const SignalsScreen()),
                      );
                    },
                  ),
                  _ActionCard(
                    title: 'News',
                    subtitle: 'Market headlines and sentiment',
                    icon: Icons.newspaper_outlined,
                    onTap: () {
                      Navigator.of(context).push(
                        MaterialPageRoute(builder: (_) => const NewsScreen()),
                      );
                    },
                  ),
                  _ActionCard(
                    title: 'Dashboard',
                    subtitle: 'Pulse and market snapshot',
                    icon: Icons.dashboard_outlined,
                    onTap: () => _reload(),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              Text(
                'Top Markets',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 12),
              FutureBuilder<List<MarketSummaryItem>>(
                future: _marketFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Padding(
                      padding: EdgeInsets.symmetric(vertical: 24),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          LinearProgressIndicator(minHeight: 2),
                          SizedBox(height: 16),
                          _PlaceholderMarketCard(symbol: 'BTCUSDT'),
                          SizedBox(height: 12),
                          _PlaceholderMarketCard(symbol: 'ETHUSDT'),
                          SizedBox(height: 12),
                          _PlaceholderMarketCard(symbol: 'SOLUSDT'),
                        ],
                      ),
                    );
                  }
                  if (snapshot.hasError) {
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 24),
                      child: Text('Market error: ${snapshot.error}'),
                    );
                  }
                  final items = snapshot.data ?? const <MarketSummaryItem>[];
                  if (items.isEmpty) {
                    return const Padding(
                      padding: EdgeInsets.symmetric(vertical: 24),
                      child: Text('Market data is not available yet.'),
                    );
                  }
                  return Column(
                    children: items
                        .map(
                          (item) => Card(
                            child: ListTile(
                              title: Text(item.symbol),
                              subtitle: Text(
                                'Price: ${item.price.toStringAsFixed(2)} | 24h: ${item.change24h.toStringAsFixed(2)}%',
                              ),
                              trailing: Text(
                                item.change24h >= 0
                                    ? '+${item.change24h.toStringAsFixed(2)}%'
                                    : '${item.change24h.toStringAsFixed(2)}%',
                                style: TextStyle(
                                  fontWeight: FontWeight.w700,
                                  color: item.change24h >= 0
                                      ? const Color(0xFF1FE36D)
                                      : const Color(0xFFFF5A7A),
                                ),
                              ),
                            ),
                          ),
                        )
                        .toList(),
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({
    required this.label,
    required this.value,
    this.sub,
  });

  final String label;
  final String value;
  final String? sub;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 150,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.74),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 4),
          Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          if (sub != null) ...[
            const SizedBox(height: 2),
            Text(sub!, style: Theme.of(context).textTheme.bodySmall),
          ],
        ],
      ),
    );
  }
}

class _ActionCard extends StatelessWidget {
  const _ActionCard({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.82),
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Colors.white12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      Theme.of(context).colorScheme.primary.withValues(alpha: 0.24),
                      Theme.of(context).colorScheme.primary.withValues(alpha: 0.08),
                    ],
                  ),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: Theme.of(context).colorScheme.primary),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                  const SizedBox(height: 4),
                  Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PlaceholderMarketCard extends StatelessWidget {
  const _PlaceholderMarketCard({required this.symbol});

  final String symbol;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        title: Text(symbol),
        subtitle: const Text('Loading market data in the background...'),
        trailing: const SizedBox(
          width: 28,
          height: 28,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      ),
    );
  }
}
