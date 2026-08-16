import 'package:flutter/material.dart';
import 'package:trademind_ai/services/trademind_api_service.dart';

class ScannerScreen extends StatefulWidget {
  const ScannerScreen({super.key});

  @override
  State<ScannerScreen> createState() => _ScannerScreenState();
}

class _ScannerScreenState extends State<ScannerScreen> {
  final TrademindApiService _apiService = TrademindApiService();
  final List<String> _symbols = const ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT'];
  String _symbol = 'BTCUSDT';
  Future<Map<String, dynamic>>? _futureScan;

  @override
  void initState() {
    super.initState();
    _futureScan = _loadScan();
  }

  Future<Map<String, dynamic>> _loadScan() {
    return _apiService.getMultiTimeframeScanner(symbol: _symbol);
  }

  void _refresh() {
    setState(() {
      _futureScan = _loadScan();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scanner')),
      body: RefreshIndicator(
        onRefresh: () async {
          _refresh();
        },
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: [
            const Text(
              'Multi-Timeframe Scanner',
              style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            const Text('Quickly inspect bullish or bearish structure across 15m, 1h, and 4h.'),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: _symbol,
              decoration: const InputDecoration(
                labelText: 'Symbol',
                border: OutlineInputBorder(),
              ),
              items: _symbols
                  .map((symbol) => DropdownMenuItem(value: symbol, child: Text(symbol)))
                  .toList(),
              onChanged: (value) {
                if (value == null) return;
                setState(() {
                  _symbol = value;
                  _futureScan = _loadScan();
                });
              },
            ),
            const SizedBox(height: 16),
            FutureBuilder<Map<String, dynamic>>(
              future: _futureScan,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 24),
                    child: LinearProgressIndicator(minHeight: 2),
                  );
                }
                if (snapshot.hasError) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 24),
                    child: Text('Scanner error: ${snapshot.error}'),
                  );
                }
                final data = snapshot.data ?? const <String, dynamic>{};
                final items = (data['items'] as List<dynamic>? ?? const []);
                if (items.isEmpty) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 24),
                    child: Text('No scan results yet.'),
                  );
                }

                final item = Map<String, dynamic>.from(items.first as Map);
                final frames = (item['timeframes'] as List<dynamic>? ?? const [])
                    .map((row) => Map<String, dynamic>.from(row as Map))
                    .toList();

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Card(
                      elevation: 0,
                      child: ListTile(
                        title: Text(item['symbol']?.toString() ?? _symbol),
                        subtitle: Text('Current scan for ${item['symbol']?.toString() ?? _symbol}'),
                      ),
                    ),
                    const SizedBox(height: 12),
                    ...frames.map(
                      (frame) => Card(
                        elevation: 0,
                        margin: const EdgeInsets.only(bottom: 12),
                        child: ListTile(
                          title: Text('${frame['interval']} • ${frame['trend']}'),
                          subtitle: Text(
                            'Strength: ${frame['strength']}'
                            '${frame.containsKey('rsi') && frame['rsi'] != null ? ' | RSI: ${frame['rsi']}' : ''}',
                          ),
                          trailing: Icon(
                            frame['trend'] == 'bullish'
                                ? Icons.trending_up
                                : frame['trend'] == 'bearish'
                                    ? Icons.trending_down
                                    : Icons.remove,
                          ),
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
