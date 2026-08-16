import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:trademind_ai/models/market_candle.dart';
import 'package:trademind_ai/services/trademind_api_service.dart';

class ChartScreen extends StatefulWidget {
  const ChartScreen({super.key});

  @override
  State<ChartScreen> createState() => _ChartScreenState();
}

class _ChartScreenState extends State<ChartScreen> {
  final TrademindApiService _apiService = TrademindApiService();
  final List<String> _symbols = const ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT'];
  final List<String> _intervals = const ['15m', '1h', '4h', '1d'];
  String _symbol = 'BTCUSDT';
  String _interval = '1h';
  Future<List<MarketCandle>>? _futureCandles;

  @override
  void initState() {
    super.initState();
    _futureCandles = _loadCandles();
  }

  Future<List<MarketCandle>> _loadCandles() {
    return _apiService.getCandles(symbol: _symbol, interval: _interval, limit: 120);
  }

  Future<void> _reload() async {
    setState(() {
      _futureCandles = _loadCandles();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Market Chart'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Live Binance Candles',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            const Text('Pick a symbol and interval, then the chart loads from the backend.'),
            const SizedBox(height: 16),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                _chipSelector(
                  options: _symbols,
                  value: _symbol,
                  onChanged: (value) {
                    setState(() {
                      _symbol = value;
                      _futureCandles = _loadCandles();
                    });
                  },
                ),
                _chipSelector(
                  options: _intervals,
                  value: _interval,
                  onChanged: (value) {
                    setState(() {
                      _interval = value;
                      _futureCandles = _loadCandles();
                    });
                  },
                ),
              ],
            ),
            const SizedBox(height: 16),
            Expanded(
              child: FutureBuilder<List<MarketCandle>>(
                future: _futureCandles,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return Center(child: Text('Chart error: ${snapshot.error}'));
                  }
                  final candles = snapshot.data ?? const <MarketCandle>[];
                  if (candles.isEmpty) {
                    return const Center(child: Text('No candle data available.'));
                  }
                  return RefreshIndicator(
                    onRefresh: _reload,
                    child: ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: [
                        _ChartCard(candles: candles),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _chipSelector({
    required List<String> options,
    required String value,
    required ValueChanged<String> onChanged,
  }) {
    return DropdownButton<String>(
      value: value,
      items: options
          .map((option) => DropdownMenuItem(value: option, child: Text(option)))
          .toList(),
      onChanged: (selected) {
        if (selected != null) {
          onChanged(selected);
        }
      },
    );
  }
}

class _ChartCard extends StatelessWidget {
  const _ChartCard({required this.candles});

  final List<MarketCandle> candles;

  @override
  Widget build(BuildContext context) {
    final spots = <FlSpot>[];
    for (var i = 0; i < candles.length; i++) {
      spots.add(FlSpot(i.toDouble(), candles[i].close));
    }

    final minY = candles.map((c) => c.low).reduce((a, b) => a < b ? a : b);
    final maxY = candles.map((c) => c.high).reduce((a, b) => a > b ? a : b);

    return Card(
      elevation: 0,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: LineChart(
          LineChartData(
            minY: minY,
            maxY: maxY,
            gridData: const FlGridData(show: true),
            borderData: FlBorderData(show: false),
            titlesData: const FlTitlesData(show: false),
            lineBarsData: [
              LineChartBarData(
                spots: spots,
                isCurved: true,
                barWidth: 3,
                color: Theme.of(context).colorScheme.primary,
                dotData: const FlDotData(show: false),
                belowBarData: BarAreaData(show: true, color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.12)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
