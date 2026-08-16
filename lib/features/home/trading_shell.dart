import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:trademind_ai/features/ai_chat/ai_chat_screen.dart';
import 'package:trademind_ai/features/liquidations/liquidations_screen.dart';
import 'package:trademind_ai/features/education/learn_trading_screen.dart';
import 'package:trademind_ai/features/market/crypto_market_screen.dart';
import 'package:trademind_ai/features/news/news_screen.dart';
import 'package:trademind_ai/features/profile/profile_screen.dart';
import 'package:trademind_ai/features/notifications/notifications_screen.dart';
import 'package:trademind_ai/features/ratio/long_short_ratio_screen.dart';
import 'package:trademind_ai/features/scanner/scanner_screen.dart';
import 'package:trademind_ai/features/signals/signals_screen.dart';
import 'package:trademind_ai/features/whales/whale_tracking_screen.dart';

class TradingShell extends StatefulWidget {
  const TradingShell({super.key});

  @override
  State<TradingShell> createState() => _TradingShellState();
}

class _TradingShellState extends State<TradingShell> {
  int _index = 0;

  final _pages = const [
    CryptoMarketScreen(),
    _DiscoverHub(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBody: true,
      body: Stack(
        children: [
          IndexedStack(index: _index, children: _pages),
          Positioned(
            left: 16,
            bottom: 92,
            child: SafeArea(
              child: FloatingActionButton.extended(
                heroTag: 'ai-chat-shell',
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => const AiChatScreen()),
                ),
                icon: const Icon(Icons.chat_bubble_outline),
                label: const Text('AI Chat'),
              ),
            ),
          ),
        ],
      ),
      bottomNavigationBar: ClipRRect(
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
          child: NavigationBar(
            selectedIndex: _index,
            onDestinationSelected: (value) => setState(() => _index = value),
            destinations: const [
              NavigationDestination(icon: Icon(Icons.pie_chart_outline), label: 'Markets'),
              NavigationDestination(icon: Icon(Icons.explore_outlined), label: 'Discover'),
              NavigationDestination(icon: Icon(Icons.person_outline), label: 'Profile'),
            ],
          ),
        ),
      ),
    );
  }
}

class _DiscoverHub extends StatelessWidget {
  const _DiscoverHub();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Discover'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 1,
            children: [
              _DiscoverSectionCard(
                title: 'News',
                subtitle: 'Market headlines',
                icon: Icons.newspaper_outlined,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => const NewsScreen()),
                ),
              ),
              _DiscoverSectionCard(
                title: 'Scanner',
                subtitle: 'Find setups',
                icon: Icons.travel_explore_outlined,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => const ScannerScreen()),
                ),
              ),
              _DiscoverSectionCard(
                title: 'Signals',
                subtitle: 'Trade calls',
                icon: Icons.candlestick_chart_outlined,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => const SignalsScreen()),
                ),
              ),
              _DiscoverSectionCard(
                title: 'Learn Trading',
                subtitle: 'Lessons from admin',
                icon: Icons.school_outlined,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => const LearnTradingScreen()),
                ),
              ),
              _DiscoverSectionCard(
                title: 'Long/Short Ratio',
                subtitle: 'Live market positioning',
                icon: Icons.compare_arrows_outlined,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => const LongShortRatioScreen()),
                ),
              ),
              _DiscoverSectionCard(
                title: 'Notifications',
                subtitle: 'In-app alerts',
                icon: Icons.notifications_outlined,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => const NotificationsScreen()),
                ),
              ),
              _DiscoverSectionCard(
                title: 'Whales',
                subtitle: 'Large transfers',
                icon: Icons.water_outlined,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => const WhaleTrackingScreen()),
                ),
              ),
              _DiscoverSectionCard(
                title: 'Liquidations',
                subtitle: 'Leverage flushes',
                icon: Icons.warning_amber_outlined,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => const LiquidationsScreen()),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _DiscoverSectionCard extends StatelessWidget {
  const _DiscoverSectionCard({
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
      color: Theme.of(context).colorScheme.surface,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                height: 42,
                width: 42,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: Theme.of(context).colorScheme.primary, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Icon(
                Icons.chevron_right,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
