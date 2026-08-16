import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:trademind_ai/features/chart/chart_screen.dart';
import 'package:trademind_ai/features/ai_chat/ai_chat_screen.dart';
import 'package:trademind_ai/features/common/feature_placeholder_screen.dart';
import 'package:trademind_ai/features/dashboard/dashboard_screen.dart';
import 'package:trademind_ai/features/market/crypto_market_screen.dart';
import 'package:trademind_ai/features/news/news_screen.dart';
import 'package:trademind_ai/features/profile/profile_screen.dart';
import 'package:trademind_ai/features/scanner/scanner_screen.dart';
import 'package:trademind_ai/features/signals/signals_screen.dart';
import 'package:trademind_ai/providers/app_providers.dart';
import 'package:trademind_ai/providers/auth_provider.dart';
import 'package:intl/intl.dart';

class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  @override
  void initState() {
    super.initState();
    unawaited(_warmUpFeeds());
  }

  Future<void> _warmUpFeeds() async {
    try {
      unawaited(ref.read(marketOverviewProvider.future));
      unawaited(ref.read(signalsProvider.future));
      unawaited(ref.read(newsProvider.future));
    } catch (_) {
      // Keep the dashboard usable even if the backend is slow or offline.
    }
  }

  void _open(Widget screen) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => screen));
  }

  @override
  Widget build(BuildContext context) {
    final market = ref.watch(marketOverviewProvider).valueOrNull;
    final news = ref.watch(newsProvider).valueOrNull;
    final signals = ref.watch(signalsProvider).valueOrNull;

    final accent = Theme.of(context).colorScheme.primary;

    return Scaffold(
      appBar: AppBar(
        title: const Text('TradeMind AI'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authServiceProvider).signOut(),
            tooltip: 'Logout',
          ),
        ],
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFFF7F8FA), Color(0xFFFFFFFF)],
          ),
        ),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              color: const Color(0xFF101828),
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Your market hub',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            color: Colors.white,
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Open any section with one tap. Live market data and news load quietly in the background.',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.white70),
                    ),
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: [
                        _MiniStat(
                          label: 'BTC',
                          value: market == null ? 'Syncing' : '\$${market.btcPrice.toStringAsFixed(0)}',
                        ),
                        _MiniStat(
                          label: 'Signals',
                          value: signals == null ? 'Syncing' : '${signals.length} ready',
                        ),
                        _MiniStat(
                          label: 'News',
                          value: news == null ? 'Syncing' : '${news.length} ready',
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 18),
            Text(
              'Quick Access',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            GridView.count(
              crossAxisCount: MediaQuery.of(context).size.width > 700 ? 3 : 2,
              shrinkWrap: true,
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              physics: const NeverScrollableScrollPhysics(),
              childAspectRatio: 1.15,
              children: [
                _ActionCard(
                  title: 'Chart',
                  subtitle: 'Candles and indicators',
                  icon: Icons.query_stats_outlined,
                  color: accent,
                  onTap: () => _open(const ChartScreen()),
                ),
                _ActionCard(
                  title: 'Signals',
                  subtitle: 'View active and closed setups',
                  icon: Icons.show_chart,
                  color: accent,
                  onTap: () => _open(const SignalsScreen()),
                ),
                _ActionCard(
                  title: 'News',
                  subtitle: 'Market headlines and sentiment',
                  icon: Icons.newspaper_outlined,
                  color: accent,
                  onTap: () => _open(const NewsScreen()),
                ),
                _ActionCard(
                  title: 'Profile',
                  subtitle: 'Account and logout',
                  icon: Icons.person_outline,
                  color: accent,
                  onTap: () => _open(const ProfileScreen()),
                ),
                _ActionCard(
                  title: 'AI Chat',
                  subtitle: 'Ask about trend setups',
                  icon: Icons.smart_toy_outlined,
                  color: accent,
                  onTap: () => _open(const AiChatScreen()),
                ),
                _ActionCard(
                  title: 'Scanner',
                  subtitle: 'Multi-timeframe scanner',
                  icon: Icons.radar_outlined,
                  color: accent,
                  onTap: () => _open(const ScannerScreen()),
                ),
                _ActionCard(
                  title: 'Crypto Market',
                  subtitle: 'Gainers, losers, favorites',
                  icon: Icons.currency_bitcoin,
                  color: accent,
                  onTap: () => _open(const CryptoMarketScreen()),
                ),
                _ActionCard(
                  title: 'Forex',
                  subtitle: 'EUR/USD and more',
                  icon: Icons.currency_exchange,
                  color: accent,
                  onTap: () => _open(const FeaturePlaceholderScreen(
                    title: 'Forex',
                    description: 'Forex analysis and news will live here.',
                    icon: Icons.currency_exchange,
                  )),
                ),
                _ActionCard(
                  title: 'Learning',
                  subtitle: 'Trading lessons and quizzes',
                  icon: Icons.menu_book_outlined,
                  color: accent,
                  onTap: () => _open(const FeaturePlaceholderScreen(
                    title: 'Learning',
                    description: 'Beginner to advanced trading lessons will appear here.',
                    icon: Icons.menu_book_outlined,
                  )),
                ),
                _ActionCard(
                  title: 'Dashboard',
                  subtitle: 'Simple market overview',
                  icon: Icons.dashboard_outlined,
                  color: accent,
                  onTap: () => _open(const DashboardScreen()),
                ),
              ],
            ),
            const SizedBox(height: 18),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Icon(Icons.sync, color: accent),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        market == null
                            ? 'Background sync is running. Open any module when you are ready.'
                            : 'Market data last refreshed at ${DateFormat('h:mm a').format(market.updatedAt)}.',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  const _MiniStat({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 110,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: Colors.white70, fontSize: 12)),
          const SizedBox(height: 4),
          Text(value, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
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
    required this.color,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(20),
      elevation: 0,
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: const Color(0xFFE7E9EF)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: color),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    style: const TextStyle(color: Colors.black54, fontSize: 12),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
