import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:trademind_ai/models/ai_chat.dart';
import 'package:trademind_ai/providers/app_providers.dart';

class AiChatScreen extends ConsumerStatefulWidget {
  const AiChatScreen({super.key});

  @override
  ConsumerState<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends ConsumerState<AiChatScreen> {
  final _controller = TextEditingController();
  final _symbolController = TextEditingController(text: 'BTCUSDT');
  final List<AiChatMessage> _messages = [
    AiChatMessage(
      role: 'assistant',
      content:
          'I am TradeMind AI. Ask me about crypto or forex setups, timeframe bias, risk, or invalidation levels.',
    ),
  ];
  String _market = 'crypto';
  String _timeframe = '4h';
  bool _sending = false;

  @override
  void dispose() {
    _controller.dispose();
    _symbolController.dispose();
    super.dispose();
  }

  Future<void> _send([String? overrideMessage]) async {
    final text = (overrideMessage ?? _controller.text).trim();
    if (text.isEmpty || _sending) {
      return;
    }

    final historyForRequest = _messages
        .where((entry) => entry.role == 'user' || entry.role == 'assistant')
        .toList()
      ..removeWhere((entry) => entry.content == _messages.first.content && entry.role == 'assistant');

    setState(() {
      _sending = true;
      _messages.add(AiChatMessage(role: 'user', content: text));
      _controller.clear();
    });

    try {
      final response = await ref.read(tradeMindApiServiceProvider).sendChatSafe({
            'message': text,
            if (historyForRequest.isNotEmpty) 'history': historyForRequest,
            'market': _market,
            if (_symbolController.text.trim().isNotEmpty)
              'symbol': _symbolController.text.trim().toUpperCase(),
            'timeframe': _timeframe,
            'context': 'TradeMind AI trading assistant for quick market analysis and risk management.',
          });

      if (!mounted) {
        return;
      }

      setState(() {
        _messages.add(AiChatMessage(role: 'assistant', content: response['reply'] as String));
      });
    } finally {
      if (mounted) {
        setState(() => _sending = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final quickPrompts = [
      'Should I long BTC?',
      'Analyze ETH on 4H',
      'What is the market bias right now?',
      'How should I manage risk on EUR/USD?',
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Chat'),
      ),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFF101828), Color(0xFF22304A)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'TradeMind AI',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                      ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Built for quick crypto and forex decision support. Keep size small and trade the structure.',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.white70),
                ),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _SelectorChip(
                      label: 'Crypto',
                      selected: _market == 'crypto',
                      onTap: () => setState(() {
                        _market = 'crypto';
                        if (_symbolController.text.trim().isEmpty || _symbolController.text == 'EURUSD') {
                          _symbolController.text = 'BTCUSDT';
                        }
                      }),
                    ),
                    _SelectorChip(
                      label: 'Forex',
                      selected: _market == 'forex',
                      onTap: () => setState(() {
                        _market = 'forex';
                        if (_symbolController.text.trim().isEmpty || _symbolController.text == 'BTCUSDT') {
                          _symbolController.text = 'EURUSD';
                        }
                      }),
                    ),
                    _SelectorChip(
                      label: '1H',
                      selected: _timeframe == '1h',
                      onTap: () => setState(() => _timeframe = '1h'),
                    ),
                    _SelectorChip(
                      label: '4H',
                      selected: _timeframe == '4h',
                      onTap: () => setState(() => _timeframe = '4h'),
                    ),
                    _SelectorChip(
                      label: '1D',
                      selected: _timeframe == '1d',
                      onTap: () => setState(() => _timeframe = '1d'),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _symbolController,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    labelText: _market == 'crypto' ? 'Symbol' : 'Pair',
                    hintText: _market == 'crypto' ? 'BTCUSDT' : 'EURUSD',
                    labelStyle: const TextStyle(color: Colors.white70),
                    hintStyle: const TextStyle(color: Colors.white38),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: Colors.white24),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: Colors.white70),
                    ),
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Quick prompts',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
              ),
            ),
          ),
          SizedBox(
            height: 48,
            child: ListView.separated(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              scrollDirection: Axis.horizontal,
              itemBuilder: (_, index) {
                final prompt = quickPrompts[index];
                return ActionChip(
                  label: Text(prompt),
                  onPressed: () => _send(prompt),
                );
              },
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemCount: quickPrompts.length,
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final message = _messages[index];
                final isUser = message.role == 'user';
                return Align(
                  alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(14),
                    constraints: const BoxConstraints(maxWidth: 560),
                    decoration: BoxDecoration(
                      color: isUser ? Theme.of(context).colorScheme.primary : Colors.white,
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: const Color(0xFFE5E7EB)),
                    ),
                    child: Text(
                      message.content,
                      style: TextStyle(
                        color: isUser ? Colors.white : Colors.black87,
                        height: 1.35,
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          Container(
            padding: EdgeInsets.fromLTRB(
              16,
              12,
              16,
              16 + MediaQuery.of(context).padding.bottom,
            ),
            decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(top: BorderSide(color: Color(0xFFE7E9EF))),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _send(),
                    decoration: const InputDecoration(
                      hintText: 'Ask TradeMind AI...',
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                FilledButton(
                  onPressed: _sending ? null : () => _send(),
                  child: Text(_sending ? 'Analyzing' : 'Send'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SelectorChip extends StatelessWidget {
  const _SelectorChip({
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
