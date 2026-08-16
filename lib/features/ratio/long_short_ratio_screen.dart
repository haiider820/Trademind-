import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class LongShortRatioScreen extends StatefulWidget {
  const LongShortRatioScreen({super.key});

  @override
  State<LongShortRatioScreen> createState() => _LongShortRatioScreenState();
}

class _LongShortRatioScreenState extends State<LongShortRatioScreen> {
  final Dio _dio = Dio();
  final _symbols = const ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'BNBUSDT'];
  late String _symbol;
  late Future<_RatioSnapshot> _future;

  @override
  void initState() {
    super.initState();
    _symbol = _symbols.first;
    _future = _load();
  }

  Future<_RatioSnapshot> _load() async {
    final longShort = await _dio.get(
      'https://fapi.binance.com/futures/data/globalLongShortAccountRatio',
      queryParameters: {'symbol': _symbol, 'period': '5m', 'limit': 1},
    );
    final openInterest = await _dio.get(
      'https://fapi.binance.com/fapi/v1/openInterest',
      queryParameters: {'symbol': _symbol},
    );
    final fundingRate = await _dio.get(
      'https://fapi.binance.com/fapi/v1/premiumIndex',
      queryParameters: {'symbol': _symbol},
    );

    final ratioRow = (longShort.data as List).cast<Map<String, dynamic>>().first;
    return _RatioSnapshot(
      symbol: _symbol,
      longAccountRatio: double.tryParse('${ratioRow['longAccountRatio']}') ?? 0,
      shortAccountRatio: double.tryParse('${ratioRow['shortAccountRatio']}') ?? 0,
      longShortRatio: double.tryParse('${ratioRow['longShortRatio']}') ?? 0,
      openInterest: double.tryParse('${openInterest.data['openInterest']}') ?? 0,
      fundingRate: double.tryParse('${fundingRate.data['lastFundingRate']}') ?? 0,
      time: DateTime.fromMillisecondsSinceEpoch((ratioRow['timestamp'] as num).toInt()),
    );
  }

  void _reload() {
    setState(() {
      _future = _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Long / Short Ratio'),
        actions: [
          IconButton(onPressed: _reload, icon: const Icon(Icons.refresh)),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            DropdownButtonFormField<String>(
              initialValue: _symbol,
              decoration: const InputDecoration(labelText: 'Symbol'),
              items: _symbols
                  .map((symbol) => DropdownMenuItem(value: symbol, child: Text(symbol)))
                  .toList(),
              onChanged: (value) {
                if (value == null) return;
                setState(() {
                  _symbol = value;
                  _future = _load();
                });
              },
            ),
            const SizedBox(height: 16),
            Expanded(
              child: FutureBuilder<_RatioSnapshot>(
                future: _future,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return Center(child: Text('Failed to load ratio: ${snapshot.error}'));
                  }

                  final data = snapshot.data;
                  if (data == null) {
                    return const Center(child: Text('No ratio data available.'));
                  }

                  return ListView(
                    children: [
                      _MetricCard(
                        title: 'Long / Short Ratio',
                        value: data.longShortRatio.toStringAsFixed(3),
                        subtitle: 'Above 1 means more long accounts',
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: _MetricCard(
                              title: 'Long Accounts',
                              value: '${(data.longAccountRatio * 100).toStringAsFixed(1)}%',
                              subtitle: 'Account share',
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _MetricCard(
                              title: 'Short Accounts',
                              value: '${(data.shortAccountRatio * 100).toStringAsFixed(1)}%',
                              subtitle: 'Account share',
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      _MetricCard(
                        title: 'Open Interest',
                        value: NumberFormat.compact().format(data.openInterest),
                        subtitle: 'Contracts currently open',
                      ),
                      const SizedBox(height: 12),
                      _MetricCard(
                        title: 'Funding Rate',
                        value: '${(data.fundingRate * 100).toStringAsFixed(4)}%',
                        subtitle: 'Last funding snapshot',
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'Updated ${DateFormat('HH:mm:ss').format(data.time)}',
                        style: const TextStyle(color: Colors.white54),
                      ),
                    ],
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.title, required this.value, required this.subtitle});

  final String title;
  final String value;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(color: Colors.white70)),
          const SizedBox(height: 8),
          Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
          const SizedBox(height: 6),
          Text(subtitle, style: const TextStyle(color: Colors.white54, fontSize: 12)),
        ],
      ),
    );
  }
}

class _RatioSnapshot {
  _RatioSnapshot({
    required this.symbol,
    required this.longAccountRatio,
    required this.shortAccountRatio,
    required this.longShortRatio,
    required this.openInterest,
    required this.fundingRate,
    required this.time,
  });

  final String symbol;
  final double longAccountRatio;
  final double shortAccountRatio;
  final double longShortRatio;
  final double openInterest;
  final double fundingRate;
  final DateTime time;
}
