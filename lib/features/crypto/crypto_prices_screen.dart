import 'package:flutter/material.dart';
import 'package:trademind_ai/services/trademind_api_service.dart';

class CryptoPricesScreen extends StatefulWidget {
  const CryptoPricesScreen({super.key});

  @override
  State<CryptoPricesScreen> createState() => _CryptoPricesScreenState();
}

class _CryptoPricesScreenState extends State<CryptoPricesScreen> {
  final TrademindApiService _apiService = TrademindApiService();
  final _searchController = TextEditingController();
  Future<List<Map<String, dynamic>>>? _futurePrices;
  List<Map<String, dynamic>> _allPrices = const [];

  @override
  void initState() {
    super.initState();
    _futurePrices = _loadPrices();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<List<Map<String, dynamic>>> _loadPrices() async {
    final items = await _apiService.getAllCryptoPrices();
    _allPrices = items;
    return items;
  }

  void _reload() {
    setState(() {
      _futurePrices = _loadPrices();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('All Cryptocurrencies')),
      body: RefreshIndicator(
        onRefresh: () async => _reload(),
        child: ListView(
          padding: const EdgeInsets.all(16),
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            const Text(
              'Live crypto prices',
              style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            const Text('Prices come directly from Binance, so they stay live and consistent.'),
            const SizedBox(height: 16),
            TextField(
              controller: _searchController,
              decoration: const InputDecoration(
                labelText: 'Search symbol',
                hintText: 'BTCUSDT',
                border: OutlineInputBorder(),
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 16),
            FutureBuilder<List<Map<String, dynamic>>>(
              future: _futurePrices,
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
                    child: Text('Price load error: ${snapshot.error}'),
                  );
                }

                final prices = snapshot.data ?? _allPrices;
                final query = _searchController.text.trim().toUpperCase();
                final filtered = query.isEmpty
                    ? prices
                    : prices
                        .where((item) => (item['symbol']?.toString() ?? '').contains(query))
                        .toList();

                if (filtered.isEmpty) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 24),
                    child: Text('No symbols match your search.'),
                  );
                }

                return Column(
                  children: filtered
                      .map(
                        (item) => Card(
                          elevation: 0,
                          child: ListTile(
                            title: Text(item['symbol']?.toString() ?? '-'),
                            subtitle: Text(
                              '24h change: ${(item['change_24h'] as num).toStringAsFixed(2)}%',
                            ),
                            trailing: Text(
                              '\$${(item['price'] as num).toStringAsFixed(4)}',
                              style: const TextStyle(fontWeight: FontWeight.w700),
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
    );
  }
}
