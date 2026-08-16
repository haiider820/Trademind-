import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:trademind_ai/models/trade_signal.dart';
import 'package:trademind_ai/providers/app_providers.dart';
import 'package:trademind_ai/services/trademind_api_service.dart';

class SignalsScreen extends ConsumerStatefulWidget {
  const SignalsScreen({super.key});

  @override
  ConsumerState<SignalsScreen> createState() => _SignalsScreenState();
}

class _SignalsScreenState extends ConsumerState<SignalsScreen> {
  String _statusFilter = 'all';
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _refreshTimer = Timer.periodic(const Duration(seconds: 15), (_) {
      if (mounted) {
        ref.invalidate(signalsProvider);
      }
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'tp_hit':
        return const Color(0xFF1FE36D);
      case 'sl_hit':
        return const Color(0xFFFF5A7A);
      case 'open':
        return const Color(0xFFFFB84D);
      default:
        return const Color(0xFF7E8AA6);
    }
  }

  List<TradeSignal> _filteredSignals(List<TradeSignal> signals) {
    if (_statusFilter == 'all') {
      return signals;
    }
    return signals.where((signal) => signal.status == _statusFilter).toList();
  }

  Future<void> _refresh() async {
    ref.invalidate(signalsProvider);
  }

  Future<void> _openCreateSheet() async {
    final messenger = ScaffoldMessenger.of(context);
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => const _SignalFormSheet(),
    );
    if (created == true && mounted) {
      await _refresh();
      messenger.showSnackBar(const SnackBar(content: Text('Signal created')));
    }
  }

  Future<void> _openSignalDetails(TradeSignal signal) async {
    final role = ref.read(currentUserRoleProvider).valueOrNull;
    final isAdmin = role == 'admin';
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => _SignalDetailSheet(signal: signal, isAdmin: isAdmin),
    );
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final signalsAsync = ref.watch(signalsProvider);
    final signals = signalsAsync.valueOrNull ?? const <TradeSignal>[];
    final filtered = _filteredSignals(signals);
    final roleAsync = ref.watch(currentUserRoleProvider);
    final role = roleAsync.valueOrNull;
    final isAdmin = role == 'admin';
    final openCount = signals.where((s) => s.status == 'open').length;
    final closedCount = signals.where((s) => s.status == 'closed').length;

    return Scaffold(
      floatingActionButton: isAdmin
          ? FloatingActionButton.extended(
              onPressed: _openCreateSheet,
              icon: const Icon(Icons.add),
              label: const Text('New Signal'),
            )
          : null,
      body: Container(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment.topCenter,
            radius: 1.3,
            colors: [Color(0xFF172033), Color(0xFF0A0D14), Color(0xFF070A10)],
          ),
        ),
        child: SafeArea(
          child: RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Signals',
                            style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            isAdmin
                                ? 'Create, review, and update trade calls from one live screen.'
                                : 'View live trade signals from the team.',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ),
                    IconButton.filledTonal(
                      onPressed: _refresh,
                      icon: const Icon(Icons.refresh),
                      tooltip: 'Refresh',
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    _SignalStatCard(label: 'Open', value: openCount.toString(), accent: const Color(0xFFFFB84D)),
                    _SignalStatCard(label: 'Closed', value: closedCount.toString(), accent: const Color(0xFF1FE36D)),
                    _SignalStatCard(
                      label: 'Access',
                      value: isAdmin ? 'Admin' : 'View',
                      accent: const Color(0xFF5F8CFF),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _FilterChip(
                      label: 'All',
                      selected: _statusFilter == 'all',
                      onTap: () => setState(() => _statusFilter = 'all'),
                    ),
                    _FilterChip(
                      label: 'Open',
                      selected: _statusFilter == 'open',
                      onTap: () => setState(() => _statusFilter = 'open'),
                    ),
                    _FilterChip(
                      label: 'TP Hit',
                      selected: _statusFilter == 'tp_hit',
                      onTap: () => setState(() => _statusFilter = 'tp_hit'),
                    ),
                    _FilterChip(
                      label: 'SL Hit',
                      selected: _statusFilter == 'sl_hit',
                      onTap: () => setState(() => _statusFilter = 'sl_hit'),
                    ),
                    _FilterChip(
                      label: 'Closed',
                      selected: _statusFilter == 'closed',
                      onTap: () => setState(() => _statusFilter = 'closed'),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                if (signalsAsync.hasError)
                  _EmptyState(
                    title: 'Failed to load signals',
                    subtitle: '${signalsAsync.error}',
                  )
                else if (roleAsync.isLoading)
                  const _EmptyState(
                    title: 'Checking access',
                    subtitle: 'Loading your role before showing signal controls.',
                  )
                else if (!isAdmin)
                  const _EmptyState(
                    title: 'View only',
                    subtitle: 'You can view live signals, but only admins can create or update them.',
                  ),
                if (signals.isEmpty)
                  const _EmptyState(
                    title: 'Signals are syncing',
                    subtitle: 'Pull to refresh or create a new signal if you have admin access.',
                  )
                else if (filtered.isEmpty)
                  const _EmptyState(
                    title: 'No matching signals',
                    subtitle: 'Switch filters to see more trade calls.',
                  )
                else
                  ...filtered.map(
                    (signal) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Card(
                        child: InkWell(
                          borderRadius: BorderRadius.circular(20),
                          onTap: () => _openSignalDetails(signal),
                          child: Padding(
                            padding: const EdgeInsets.all(14),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        '${signal.pair} ${signal.tradeType.toUpperCase()}',
                                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                                      ),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                      decoration: BoxDecoration(
                                        color: _statusColor(signal.status).withValues(alpha: 0.14),
                                        borderRadius: BorderRadius.circular(999),
                                      ),
                                      child: Text(
                                        signal.status.toUpperCase(),
                                        style: TextStyle(
                                          color: _statusColor(signal.status),
                                          fontWeight: FontWeight.w800,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 12),
                                Wrap(
                                  spacing: 12,
                                  runSpacing: 8,
                                  children: [
                                    _SignalPill(label: 'Entry', value: signal.entry.toStringAsFixed(4)),
                                    _SignalPill(label: 'TP', value: signal.tp.toStringAsFixed(4)),
                                    _SignalPill(label: 'SL', value: signal.sl.toStringAsFixed(4)),
                                    _SignalPill(label: 'Risk', value: signal.riskLevel.toUpperCase()),
                                  ],
                                ),
                                const SizedBox(height: 12),
                                Row(
                                  children: [
                                    Chip(label: Text('${signal.pnl.toStringAsFixed(2)}% PnL')),
                                    const SizedBox(width: 8),
                                    Text(
                                      isAdmin ? 'Tap for actions' : 'Details',
                                      style: Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({
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

class _SignalStatCard extends StatelessWidget {
  const _SignalStatCard({
    required this.label,
    required this.value,
    required this.accent,
  });

  final String label;
  final String value;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 104,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.82),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: accent.withValues(alpha: 0.18)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 6),
          Text(value, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: accent)),
        ],
      ),
    );
  }
}

class _SignalPill extends StatelessWidget {
  const _SignalPill({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 2),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({
    required this.title,
    required this.subtitle,
  });

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 20),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.insights_outlined, size: 42, color: Colors.white54),
            const SizedBox(height: 10),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(subtitle, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _SignalDetailSheet extends ConsumerWidget {
  const _SignalDetailSheet({required this.signal, required this.isAdmin});

  final TradeSignal signal;
  final bool isAdmin;

  Future<void> _updateStatus(
    BuildContext context,
    WidgetRef ref,
    String status,
  ) async {
    try {
      final response = await ref.read(tradeMindApiServiceProvider).updateSignal(
            signal.id,
            {'status': status},
          );
      final updated = response['data'] as Map<String, dynamic>?;
      if (context.mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              updated == null
                  ? 'Signal updated'
                  : 'Signal ${updated['pair'] ?? signal.pair} marked as ${status.replaceAll('_', ' ')}',
            ),
          ),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Update failed: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
        top: 8,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${signal.pair} ${signal.tradeType.toUpperCase()}',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          Text('Entry: ${signal.entry}'),
          Text('TP: ${signal.tp}'),
          Text('SL: ${signal.sl}'),
          Text('Risk: ${signal.riskLevel.toUpperCase()}'),
          Text('PnL: ${signal.pnl.toStringAsFixed(2)}%'),
          const SizedBox(height: 16),
          if (isAdmin) ...[
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton(
                  onPressed: signal.status == 'tp_hit' ? null : () => _updateStatus(context, ref, 'tp_hit'),
                  child: const Text('Mark TP Hit'),
                ),
                FilledButton.tonal(
                  onPressed: signal.status == 'sl_hit' ? null : () => _updateStatus(context, ref, 'sl_hit'),
                  child: const Text('Mark SL Hit'),
                ),
                OutlinedButton(
                  onPressed: signal.status == 'closed' ? null : () => _updateStatus(context, ref, 'closed'),
                  child: const Text('Close Signal'),
                ),
              ],
            ),
          ] else ...[
            const Text('This signal is view-only for regular users.'),
          ],
          const SizedBox(height: 16),
        ],
      ),
    );
  }
}

class _SignalFormSheet extends ConsumerStatefulWidget {
  const _SignalFormSheet();

  @override
  ConsumerState<_SignalFormSheet> createState() => _SignalFormSheetState();
}

class _SignalFormSheetState extends ConsumerState<_SignalFormSheet> {
  final _formKey = GlobalKey<FormState>();
  final _pairController = TextEditingController();
  final _entryController = TextEditingController();
  final _slController = TextEditingController();
  final _tpController = TextEditingController();
  final _apiService = TrademindApiService();
  String _tradeType = 'long';
  String _riskLevel = 'medium';
  bool _saving = false;
  bool _loadingSymbols = true;
  String _query = '';
  List<Map<String, dynamic>> _symbols = const [];
  Map<String, dynamic>? _selectedSymbol;

  @override
  void initState() {
    super.initState();
    _pairController.addListener(() {
      final next = _pairController.text.trim().toUpperCase();
      if (next == _query) return;
      setState(() {
        _query = next;
        _selectedSymbol = null;
      });
    });
    _loadSymbols();
  }

  Future<void> _loadSymbols() async {
    try {
      final items = await _apiService.getAllCryptoPrices();
      if (!mounted) return;
      setState(() {
        _symbols = items;
        _loadingSymbols = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingSymbols = false;
      });
    }
  }

  @override
  void dispose() {
    _pairController.dispose();
    _entryController.dispose();
    _slController.dispose();
    _tpController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() => _saving = true);
    try {
      await ref.read(tradeMindApiServiceProvider).createSignal({
            'pair': _pairController.text.trim().toUpperCase(),
            'trade_type': _tradeType,
            'entry': double.parse(_entryController.text),
            'sl': double.parse(_slController.text),
            'tp': double.parse(_tpController.text),
            'risk_level': _riskLevel,
          });
      if (mounted) {
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) {
        String message = e.toString().replaceFirst('Bad state: ', '');
        if (e is DioException) {
          final status = e.response?.statusCode;
          final data = e.response?.data;
          message = 'Create failed${status != null ? ' ($status)' : ''}: $data';
        }
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message)),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  List<Map<String, dynamic>> _matchingSymbols() {
    if (_symbols.isEmpty) {
      return const [];
    }
    if (_query.isEmpty) {
      return _symbols.take(10).toList();
    }
    return _symbols
        .where((item) {
          final symbol = item['symbol']?.toString().toUpperCase() ?? '';
          return symbol.contains(_query);
        })
        .take(10)
        .toList();
  }

  void _selectSymbol(Map<String, dynamic> item) {
    final symbol = item['symbol']?.toString().toUpperCase() ?? '';
    final price = (item['price'] as num?)?.toDouble() ?? 0;
    setState(() {
      _selectedSymbol = item;
      _pairController.text = symbol;
      _pairController.selection = TextSelection.collapsed(offset: symbol.length);
      _query = symbol;
      if (_entryController.text.trim().isEmpty && price > 0) {
        _entryController.text = price.toStringAsFixed(4);
      }
      if (_slController.text.trim().isEmpty && price > 0) {
        _slController.text = (price * 0.98).toStringAsFixed(4);
      }
      if (_tpController.text.trim().isEmpty && price > 0) {
        _tpController.text = (price * 1.02).toStringAsFixed(4);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final matches = _matchingSymbols();

    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
        top: 8,
      ),
      child: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Create Signal',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _pairController,
                decoration: const InputDecoration(
                  labelText: 'Pair',
                  hintText: 'Type BTC, ETH, SOL...',
                  prefixIcon: Icon(Icons.search),
                ),
                validator: (value) => value == null || value.trim().isEmpty ? 'Enter pair' : null,
              ),
              const SizedBox(height: 12),
              if (_loadingSymbols)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 4),
                  child: LinearProgressIndicator(minHeight: 2),
                )
              else if (_pairController.text.trim().isNotEmpty)
                Container(
                  constraints: const BoxConstraints(maxHeight: 240),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surface,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: Colors.white12),
                  ),
                  child: matches.isEmpty
                      ? const Padding(
                          padding: EdgeInsets.all(12),
                          child: Text('No matching crypto symbols found.'),
                        )
                      : ListView.separated(
                          shrinkWrap: true,
                          itemCount: matches.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (context, index) {
                            final item = matches[index];
                            final symbol = item['symbol']?.toString().toUpperCase() ?? '';
                            final price = (item['price'] as num?)?.toDouble() ?? 0;
                            final change = (item['change_24h'] as num?)?.toDouble() ?? 0;
                            return ListTile(
                              dense: true,
                              onTap: () => _selectSymbol(item),
                              title: Text(symbol),
                              subtitle: Text('Live: \$${price.toStringAsFixed(4)} | 24h: ${change.toStringAsFixed(2)}%'),
                              trailing: const Icon(Icons.arrow_forward_ios, size: 14),
                            );
                          },
                        ),
                ),
              if (_selectedSymbol != null) ...[
                const SizedBox(height: 12),
                Card(
                  child: ListTile(
                    title: Text(_selectedSymbol!['symbol']?.toString().toUpperCase() ?? ''),
                    subtitle: Text(
                      'Live price: \$${((_selectedSymbol!['price'] as num?)?.toDouble() ?? 0).toStringAsFixed(4)}',
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _tradeType,
                decoration: const InputDecoration(labelText: 'Trade Type'),
                items: const [
                  DropdownMenuItem(value: 'long', child: Text('Long')),
                  DropdownMenuItem(value: 'short', child: Text('Short')),
                ],
                onChanged: (value) => setState(() => _tradeType = value ?? 'long'),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _entryController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Entry'),
                validator: _validateNumber,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _slController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Stop Loss'),
                validator: _validateNumber,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _tpController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Take Profit'),
                validator: _validateNumber,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _riskLevel,
                decoration: const InputDecoration(labelText: 'Risk Level'),
                items: const [
                  DropdownMenuItem(value: 'low', child: Text('Low')),
                  DropdownMenuItem(value: 'medium', child: Text('Medium')),
                  DropdownMenuItem(value: 'high', child: Text('High')),
                ],
                onChanged: (value) => setState(() => _riskLevel = value ?? 'medium'),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _saving ? null : _submit,
                  child: Text(_saving ? 'Saving...' : 'Create Signal'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String? _validateNumber(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Enter a number';
    }
    if (double.tryParse(value.trim()) == null) {
      return 'Invalid number';
    }
    return null;
  }
}
