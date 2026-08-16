import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

class BinancePriceTick {
  BinancePriceTick({
    required this.symbol,
    required this.price,
    required this.change24h,
    required this.volume24h,
  });

  final String symbol;
  final double price;
  final double change24h;
  final double volume24h;
}

class BinanceWsService {
  WebSocketChannel? _channel;
  final _controller = StreamController<BinancePriceTick>.broadcast();

  Stream<BinancePriceTick> get stream => _controller.stream;

  void connect(String symbol) {
    disconnect();
    final normalized = symbol.toLowerCase();
    _channel = WebSocketChannel.connect(
      Uri.parse('wss://stream.binance.com:9443/ws/$normalized@ticker'),
    );
    _channel!.stream.listen(
      (event) {
        try {
          final data = jsonDecode(event as String) as Map<String, dynamic>;
          _controller.add(
            BinancePriceTick(
              symbol: (data['s'] as String?) ?? symbol.toUpperCase(),
              price: double.tryParse(data['c']?.toString() ?? '') ?? 0,
              change24h: double.tryParse(data['P']?.toString() ?? '') ?? 0,
              volume24h: double.tryParse(data['v']?.toString() ?? '') ?? 0,
            ),
          );
        } catch (_) {}
      },
      onError: (_) {},
      onDone: () {},
    );
  }

  void disconnect() {
    _channel?.sink.close();
    _channel = null;
  }

  void dispose() {
    disconnect();
    _controller.close();
  }
}
