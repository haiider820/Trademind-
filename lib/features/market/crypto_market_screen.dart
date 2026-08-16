import 'dart:async';
import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:trademind_ai/features/market/asset_detail_screen.dart';
import 'package:trademind_ai/services/binance_ws_service.dart';
import 'package:trademind_ai/services/trademind_api_service.dart';

String _symbolBadge(String symbol) {
  final base = symbol.replaceAll('USDT', '');
  if (base.isEmpty) {
    return symbol.length <= 4 ? symbol : symbol.substring(0, 4);
  }
  return base.length <= 4 ? base : base.substring(0, 4);
}

class CryptoMarketScreen extends StatefulWidget {
  const CryptoMarketScreen({super.key});

  @override
  State<CryptoMarketScreen> createState() => _CryptoMarketScreenState();
}

class _CryptoMarketScreenState extends State<CryptoMarketScreen> {
  final TrademindApiService _apiService = TrademindApiService();
  final BinanceWsService _wsService = BinanceWsService();
  final TextEditingController _searchController = TextEditingController();
  late final Future<Box> _favoritesBoxFuture;

  Future<List<Map<String, dynamic>>>? _futurePrices;
  List<Map<String, dynamic>> _allPrices = const [];
  Set<String> _favorites = {};
  StreamSubscription<BinancePriceTick>? _wsSub;
  BinancePriceTick? _liveTick;
  String _selectedSymbol = 'BTCUSDT';
  String _filter = 'watchlist';

  @override
  void initState() {
    super.initState();
    _favoritesBoxFuture = Hive.openBox('favorites');
    _futurePrices = _loadPrices();
    _loadFavorites();
    _startWs(_selectedSymbol);
  }

  @override
  void dispose() {
    _searchController.dispose();
    _wsSub?.cancel();
    _wsService.dispose();
    super.dispose();
  }

  Future<List<Map<String, dynamic>>> _loadPrices() async {
    final items = await _apiService.getAllCryptoPrices();
    _allPrices = items;
    return items;
  }

  Future<void> _reload() async {
    setState(() {
      _futurePrices = _loadPrices();
    });
    await _futurePrices;
  }

  Future<void> _loadFavorites() async {
    final box = await _favoritesBoxFuture;
    if (!mounted) return;
    setState(() {
      _favorites = Set<String>.from((box.get('symbols') as List?) ?? const []);
    });
  }

  Future<void> _toggleFavorite(String symbol) async {
    final box = await _favoritesBoxFuture;
    final updated = Set<String>.from(_favorites);
    if (updated.contains(symbol)) {
      updated.remove(symbol);
    } else {
      updated.add(symbol);
    }
    await box.put('symbols', updated.toList());
    if (mounted) {
      setState(() {
        _favorites = updated;
      });
    }
  }

  void _startWs(String symbol) {
    _wsSub?.cancel();
    _wsService.connect(symbol);
    _wsSub = _wsService.stream.listen((tick) {
      if (!mounted) return;
      setState(() => _liveTick = tick);
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment.topCenter,
            radius: 1.55,
            colors: [
              Color(0xFF182133),
              Color(0xFF0B1018),
              Color(0xFF070A10),
            ],
          ),
        ),
        child: SafeArea(
          child: RefreshIndicator(
            onRefresh: _reload,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Markets',
                            style: theme.textTheme.headlineMedium?.copyWith(
                              fontWeight: FontWeight.w900,
                              letterSpacing: -0.4,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'Curated watchlist cards with live pricing, tiny trend lines, and fast detail access.',
                            style: theme.textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ),
                    IconButton.filledTonal(
                      onPressed: _reload,
                      icon: const Icon(Icons.refresh),
                      tooltip: 'Refresh markets',
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                if (_liveTick != null) ...[
                  _LiveTickerCard(tick: _liveTick!),
                  const SizedBox(height: 16),
                ],
                Row(
                  children: [
                    _MiniMetric(
                      label: 'Watchlist',
                      value: _favorites.length.toString().padLeft(2, '0'),
                      color: const Color(0xFFFFB84D),
                    ),
                    const SizedBox(width: 12),
                    _MiniMetric(
                      label: 'Focused',
                      value: _selectedSymbol.replaceAll('USDT', ''),
                      color: const Color(0xFF5F8CFF),
                    ),
                    const SizedBox(width: 12),
                    _MiniMetric(
                      label: 'Mode',
                      value: _filterTitle,
                      color: const Color(0xFF1FE36D),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _searchController,
                  decoration: const InputDecoration(
                    labelText: 'Search watchlist or market symbol',
                    hintText: 'BTCUSDT',
                    prefixIcon: Icon(Icons.search),
                  ),
                  onChanged: (_) => setState(() {}),
                ),
                const SizedBox(height: 12),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _MarketFilterChip(
                        label: 'Watchlist',
                        selected: _filter == 'watchlist',
                        onTap: () => setState(() => _filter = 'watchlist'),
                      ),
                      const SizedBox(width: 8),
                      _MarketFilterChip(
                        label: 'All',
                        selected: _filter == 'all',
                        onTap: () => setState(() => _filter = 'all'),
                      ),
                      const SizedBox(width: 8),
                      _MarketFilterChip(
                        label: 'Gainers',
                        selected: _filter == 'gainers',
                        onTap: () => setState(() => _filter = 'gainers'),
                      ),
                      const SizedBox(width: 8),
                      _MarketFilterChip(
                        label: 'Losers',
                        selected: _filter == 'losers',
                        onTap: () => setState(() => _filter = 'losers'),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                FutureBuilder<List<Map<String, dynamic>>>(
                  future: _futurePrices,
                  builder: (context, snapshot) {
                    if (snapshot.connectionState == ConnectionState.waiting) {
                      return const Padding(
                        padding: EdgeInsets.symmetric(vertical: 32),
                        child: Center(child: CircularProgressIndicator()),
                      );
                    }
                    if (snapshot.hasError) {
                      return _EmptyState(
                        title: 'Market load error',
                        subtitle: '${snapshot.error}',
                        icon: Icons.error_outline,
                      );
                    }

                    final prices = snapshot.data ?? _allPrices;
                    final query = _searchController.text.trim().toUpperCase();
                    var filtered = prices.where((item) {
                      final symbol = item['symbol']?.toString() ?? '';
                      return query.isEmpty || symbol.contains(query);
                    }).toList();

                    if (_filter == 'watchlist') {
                      filtered = filtered.where((item) => _favorites.contains(item['symbol']?.toString() ?? '')).toList();
                    } else if (_filter == 'gainers') {
                      filtered.sort((a, b) {
                        final av = (a['change_24h'] as num?)?.toDouble() ?? 0;
                        final bv = (b['change_24h'] as num?)?.toDouble() ?? 0;
                        return bv.compareTo(av);
                      });
                    } else if (_filter == 'losers') {
                      filtered.sort((a, b) {
                        final av = (a['change_24h'] as num?)?.toDouble() ?? 0;
                        final bv = (b['change_24h'] as num?)?.toDouble() ?? 0;
                        return av.compareTo(bv);
                      });
                    } else {
                      filtered.sort((a, b) {
                        final av = a['symbol']?.toString() ?? '';
                        final bv = b['symbol']?.toString() ?? '';
                        return av.compareTo(bv);
                      });
                    }

                    if (filtered.isEmpty) {
                      return const _EmptyState(
                        title: 'No markets found',
                        subtitle: 'Try a broader search or switch the filter.',
                        icon: Icons.search_off,
                      );
                    }

                    final topCards = filtered.take(12).toList();
                    final moversSource = _filter == 'watchlist' ? prices.toList() : filtered.toList();
                    moversSource.sort((a, b) {
                      final av = ((a['change_24h'] as num?)?.toDouble() ?? 0).abs();
                      final bv = ((b['change_24h'] as num?)?.toDouble() ?? 0).abs();
                      return bv.compareTo(av);
                    });
                    final movers = moversSource.take(6).toList();

                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _filter == 'watchlist' ? 'Watchlist' : 'Top Market Cards',
                          style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
                        ),
                        const SizedBox(height: 10),
                        ...topCards.map((item) => Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: _TickerCard(
                                item: item,
                                isFavorite: _favorites.contains(item['symbol']?.toString() ?? ''),
                                selected: _selectedSymbol == item['symbol']?.toString(),
                                onFavoriteTap: () => _toggleFavorite(item['symbol']?.toString() ?? ''),
                                onTap: () {
                                  final symbol = item['symbol']?.toString() ?? '';
                                  if (symbol.isEmpty) return;
                                  setState(() {
                                    _selectedSymbol = symbol;
                                    _startWs(symbol);
                                  });
                                  Navigator.of(context).push(
                                    MaterialPageRoute<void>(
                                      builder: (_) => AssetDetailScreen(symbol: symbol),
                                    ),
                                  );
                                },
                              ),
                            )),
                        const SizedBox(height: 8),
                        Text(
                          'Momentum movers',
                          style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
                        ),
                        const SizedBox(height: 10),
                        ...movers.map((item) => Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: _MoverRow(
                                item: item,
                                isFavorite: _favorites.contains(item['symbol']?.toString() ?? ''),
                                onFavoriteTap: () => _toggleFavorite(item['symbol']?.toString() ?? ''),
                                onTap: () {
                                  final symbol = item['symbol']?.toString() ?? '';
                                  if (symbol.isEmpty) return;
                                  setState(() {
                                    _selectedSymbol = symbol;
                                    _startWs(symbol);
                                  });
                                  Navigator.of(context).push(
                                    MaterialPageRoute<void>(
                                      builder: (_) => AssetDetailScreen(symbol: symbol),
                                    ),
                                  );
                                },
                              ),
                            )),
                      ],
                    );
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String get _filterTitle {
    switch (_filter) {
      case 'watchlist':
        return 'Watchlist';
      case 'gainers':
        return 'Gainers';
      case 'losers':
        return 'Losers';
      default:
        return 'All';
    }
  }
}

class _TickerCard extends StatelessWidget {
  const _TickerCard({
    required this.item,
    required this.isFavorite,
    required this.selected,
    required this.onFavoriteTap,
    required this.onTap,
  });

  final Map<String, dynamic> item;
  final bool isFavorite;
  final bool selected;
  final VoidCallback onFavoriteTap;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final symbol = item['symbol']?.toString() ?? '';
    final price = (item['price'] as num?)?.toDouble() ?? 0;
    final change = (item['change_24h'] as num?)?.toDouble() ?? 0;
    final volume = (item['volume_24h'] as num?)?.toDouble() ?? 0;
    final color = change >= 0 ? const Color(0xFF1FE36D) : const Color(0xFFFF5A7A);
    final seed = _seedFromSymbol(symbol);
    final points = _sparkPoints(seed, change);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(24),
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Theme.of(context).colorScheme.surface.withValues(alpha: selected ? 0.98 : 0.86),
                color.withValues(alpha: 0.12),
              ],
            ),
            border: Border.all(
              color: selected ? color.withValues(alpha: 0.55) : color.withValues(alpha: 0.14),
              width: selected ? 1.4 : 1,
            ),
            boxShadow: [
              BoxShadow(
                color: color.withValues(alpha: 0.08),
                blurRadius: 18,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: Stack(
            children: [
              Positioned.fill(
                child: IgnorePointer(
                  child: Opacity(
                    opacity: 0.82,
                    child: Padding(
                      padding: const EdgeInsets.only(left: 76, top: 6, right: 8, bottom: 4),
                      child: SparklineChart(
                        points: points,
                        lineColor: color,
                        fillColor: color.withValues(alpha: 0.08),
                      ),
                    ),
                  ),
                ),
              ),
              Row(
                children: [
                  Container(
                    width: 54,
                    height: 54,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: RadialGradient(
                        colors: [
                          color.withValues(alpha: 0.32),
                          color.withValues(alpha: 0.08),
                        ],
                      ),
                      border: Border.all(color: color.withValues(alpha: 0.18)),
                    ),
                    child: Center(
                      child: Text(
                        _symbolBadge(symbol),
                        maxLines: 1,
                        style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 12),
                      ),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                symbol,
                                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                      fontWeight: FontWeight.w900,
                                    ),
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                              decoration: BoxDecoration(
                                color: color.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: Text(
                                '${change >= 0 ? '+' : ''}${change.toStringAsFixed(2)}%',
                                style: TextStyle(
                                  color: color,
                                  fontWeight: FontWeight.w800,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Vol ${_compactNumber(volume)}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: 8),
                        Stack(
                          alignment: Alignment.centerLeft,
                          children: [
                            Positioned.fill(
                              child: Align(
                                alignment: Alignment.centerLeft,
                                child: Container(
                                  height: 48,
                                  decoration: BoxDecoration(
                                    borderRadius: BorderRadius.circular(16),
                                    color: Colors.white.withValues(alpha: 0.03),
                                  ),
                                ),
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    '\$${price.toStringAsFixed(price >= 1 ? 2 : 4)}',
                                    style: const TextStyle(
                                      fontSize: 22,
                                      fontWeight: FontWeight.w900,
                                      height: 1.0,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Live watch card',
                                    style: Theme.of(context).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Column(
                    children: [
                      IconButton(
                        onPressed: onFavoriteTap,
                        icon: Icon(
                          isFavorite ? Icons.star_rounded : Icons.star_border_rounded,
                          color: isFavorite ? const Color(0xFFFFB84D) : null,
                        ),
                      ),
                      const SizedBox(height: 14),
                      Icon(
                        selected ? Icons.fiber_manual_record : Icons.chevron_right_rounded,
                        color: selected ? color : Colors.white38,
                        size: 18,
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  int _seedFromSymbol(String symbol) {
    return symbol.runes.fold<int>(0, (previousValue, element) => previousValue + element);
  }

  List<FlSpot> _sparkPoints(int seed, double change) {
    final rng = math.Random(seed);
    var base = 1.0;
    final directionBias = change >= 0 ? 0.18 : -0.18;
    return List.generate(18, (index) {
      base += (rng.nextDouble() - 0.5) * 0.28 + directionBias * 0.08;
      base = base.clamp(0.25, 1.8);
      return FlSpot(index.toDouble(), base);
    });
  }

  static String _compactNumber(double value) {
    if (value >= 1e9) return '${(value / 1e9).toStringAsFixed(2)}B';
    if (value >= 1e6) return '${(value / 1e6).toStringAsFixed(2)}M';
    if (value >= 1e3) return '${(value / 1e3).toStringAsFixed(2)}K';
    if (value == 0) return '0';
    return value.toStringAsFixed(value < 1 ? 4 : 2);
  }
}

class _MoverRow extends StatelessWidget {
  const _MoverRow({
    required this.item,
    required this.isFavorite,
    required this.onFavoriteTap,
    required this.onTap,
  });

  final Map<String, dynamic> item;
  final bool isFavorite;
  final VoidCallback onFavoriteTap;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final symbol = item['symbol']?.toString() ?? '';
    final price = (item['price'] as num?)?.toDouble() ?? 0;
    final change = (item['change_24h'] as num?)?.toDouble() ?? 0;
    final color = change >= 0 ? const Color(0xFF1FE36D) : const Color(0xFFFF5A7A);

    return Card(
      margin: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Center(
                  child: Text(
                    _symbolBadge(symbol),
                    maxLines: 1,
                    style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 11),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(symbol, style: Theme.of(context).textTheme.titleSmall),
                    const SizedBox(height: 4),
                    Text(
                      '\$${price.toStringAsFixed(price >= 1 ? 2 : 4)}',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '${change >= 0 ? '+' : ''}${change.toStringAsFixed(2)}%',
                    style: TextStyle(color: color, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Tap for chart',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
              IconButton(
                onPressed: onFavoriteTap,
                icon: Icon(
                  isFavorite ? Icons.star_rounded : Icons.star_border_rounded,
                  color: isFavorite ? const Color(0xFFFFB84D) : null,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LiveTickerCard extends StatelessWidget {
  const _LiveTickerCard({required this.tick});

  final BinancePriceTick tick;

  @override
  Widget build(BuildContext context) {
    final color = tick.change24h >= 0 ? const Color(0xFF1FE36D) : const Color(0xFFFF5A7A);
    return Card(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              color.withValues(alpha: 0.16),
              Theme.of(context).colorScheme.surface.withValues(alpha: 0.92),
            ],
          ),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          children: [
            Container(
              width: 54,
              height: 54,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: color.withValues(alpha: 0.12),
              ),
              child: Icon(Icons.graphic_eq_rounded, color: color),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          tick.symbol,
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
                        ),
                      ),
                      Text(
                        '${tick.change24h >= 0 ? '+' : ''}${tick.change24h.toStringAsFixed(2)}%',
                        style: TextStyle(color: color, fontWeight: FontWeight.w800),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '\$${tick.price.toStringAsFixed(tick.price >= 1 ? 2 : 4)}',
                    style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w900, height: 1.0),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '24h volume ${_compactNumber(tick.volume24h)}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _compactNumber(double value) {
    if (value >= 1e9) return '${(value / 1e9).toStringAsFixed(2)}B';
    if (value >= 1e6) return '${(value / 1e6).toStringAsFixed(2)}M';
    if (value >= 1e3) return '${(value / 1e3).toStringAsFixed(2)}K';
    return value.toStringAsFixed(2);
  }
}

class _MiniMetric extends StatelessWidget {
  const _MiniMetric({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.84),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: color.withValues(alpha: 0.16)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 6),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: color, fontSize: 16, fontWeight: FontWeight.w900),
            ),
          ],
        ),
      ),
    );
  }
}

class SparklineChart extends StatelessWidget {
  const SparklineChart({
    super.key,
    required this.points,
    required this.lineColor,
    required this.fillColor,
  });

  final List<FlSpot> points;
  final Color lineColor;
  final Color fillColor;

  @override
  Widget build(BuildContext context) {
    if (points.length < 2) return const SizedBox.shrink();
    final minY = points.map((e) => e.y).reduce(math.min);
    final maxY = points.map((e) => e.y).reduce(math.max);
    final spread = (maxY - minY).abs();
    return LineChart(
      LineChartData(
        minX: 0,
        maxX: (points.length - 1).toDouble(),
        minY: minY - (spread == 0 ? 0.2 : spread * 0.2),
        maxY: maxY + (spread == 0 ? 0.2 : spread * 0.2),
        gridData: const FlGridData(show: false),
        titlesData: const FlTitlesData(show: false),
        borderData: FlBorderData(show: false),
        lineTouchData: const LineTouchData(enabled: false),
        lineBarsData: [
          LineChartBarData(
            spots: points,
            isCurved: true,
            color: lineColor,
            barWidth: 2.2,
            isStrokeCapRound: true,
            dotData: const FlDotData(show: false),
            belowBarData: BarAreaData(
              show: true,
              color: fillColor,
            ),
          ),
        ],
      ),
    );
  }
}

class _MarketFilterChip extends StatelessWidget {
  const _MarketFilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onTap(),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({
    required this.title,
    required this.subtitle,
    required this.icon,
  });

  final String title;
  final String subtitle;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 28),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 44, color: Colors.white54),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
