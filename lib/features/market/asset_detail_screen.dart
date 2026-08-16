import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:trademind_ai/models/market_candle.dart';
import 'package:trademind_ai/services/trademind_api_service.dart';

class AssetDetailScreen extends StatefulWidget {
  const AssetDetailScreen({super.key, required this.symbol});

  final String symbol;

  @override
  State<AssetDetailScreen> createState() => _AssetDetailScreenState();
}

class _AssetDetailScreenState extends State<AssetDetailScreen> {
  final TrademindApiService _apiService = TrademindApiService();
  final _intervals = const ['15m', '1h', '4h', '1d'];
  late String _interval;
  late Future<List<MarketCandle>> _futureCandles;
  int? _hoverIndex;
  int _visibleStart = 0;
  int _visibleCount = 60;

  @override
  void initState() {
    super.initState();
    _interval = '1h';
    _futureCandles = _loadCandles();
  }

  Future<List<MarketCandle>> _loadCandles() {
    return _apiService.getCandles(symbol: widget.symbol, interval: _interval, limit: 120);
  }

  void _reload() {
    setState(() {
      _futureCandles = _loadCandles();
      _hoverIndex = null;
      _visibleStart = 0;
    });
  }

  void _resetWindow(int candleCount) {
    _visibleCount = math.min(60, candleCount.clamp(20, 120));
    _visibleStart = math.max(0, candleCount - _visibleCount);
  }

  void _zoom(bool zoomIn, int candleCount) {
    setState(() {
      final next = zoomIn ? (_visibleCount - 10) : (_visibleCount + 10);
      _visibleCount = next.clamp(20, candleCount).toInt();
      _visibleStart = _visibleStart.clamp(0, math.max(0, candleCount - _visibleCount));
      _hoverIndex = null;
    });
  }

  void _shiftWindow(int delta, int candleCount) {
    setState(() {
      _visibleStart = (_visibleStart + delta).clamp(0, math.max(0, candleCount - _visibleCount));
      _hoverIndex = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.symbol)),
      body: FutureBuilder<List<MarketCandle>>(
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
            return const Center(child: Text('No OHLC data available.'));
          }
          if (_visibleStart == 0 && _visibleCount == 60) {
            _resetWindow(candles.length);
          } else {
            _visibleStart = _visibleStart.clamp(0, math.max(0, candles.length - 1));
            _visibleCount = _visibleCount.clamp(20, candles.length);
            if (_visibleStart + _visibleCount > candles.length) {
              _visibleStart = math.max(0, candles.length - _visibleCount);
            }
          }

          final visibleEnd = math.min(candles.length, _visibleStart + _visibleCount);
          final visibleCandles = candles.sublist(_visibleStart, visibleEnd);

          final latest = candles.last;
          final first = candles.first;
          final change = latest.close - first.open;
          final changePct = first.open == 0 ? 0.0 : (change / first.open) * 100;
          final isUp = change >= 0;

          return RefreshIndicator(
            onRefresh: () async => _reload(),
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              children: [
                Text(widget.symbol, style: Theme.of(context).textTheme.headlineMedium),
                const SizedBox(height: 8),
                Text(
                  '\$${latest.close.toStringAsFixed(4)}  ${isUp ? '▲' : '▼'} ${change.abs().toStringAsFixed(4)} (${changePct.abs().toStringAsFixed(2)}%)',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: isUp ? Colors.greenAccent : Colors.redAccent,
                  ),
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  children: _intervals
                      .map(
                        (interval) => ChoiceChip(
                          label: Text(interval),
                          selected: _interval == interval,
                          onSelected: (_) {
                            setState(() {
                              _interval = interval;
                              _futureCandles = _loadCandles();
                              _hoverIndex = null;
                              _visibleStart = 0;
                              _visibleCount = 60;
                            });
                          },
                        ),
                      )
                      .toList(),
                ),
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            IconButton(
                              tooltip: 'Move backward',
                              onPressed: _visibleStart == 0 ? null : () => _shiftWindow(-10, candles.length),
                              icon: const Icon(Icons.arrow_back_ios_new, size: 18),
                            ),
                            IconButton(
                              tooltip: 'Zoom out',
                              onPressed: () => _zoom(false, candles.length),
                              icon: const Icon(Icons.remove_circle_outline),
                            ),
                            IconButton(
                              tooltip: 'Zoom in',
                              onPressed: () => _zoom(true, candles.length),
                              icon: const Icon(Icons.add_circle_outline),
                            ),
                            IconButton(
                              tooltip: 'Move forward',
                              onPressed: visibleEnd >= candles.length ? null : () => _shiftWindow(10, candles.length),
                              icon: const Icon(Icons.arrow_forward_ios, size: 18),
                            ),
                          ],
                        ),
                        SizedBox(
                          height: 360,
                          child: _ChartPanel(
                            candles: visibleCandles,
                            hoveredIndex: _hoverIndex == null
                                ? null
                                : (_hoverIndex! >= _visibleStart && _hoverIndex! < visibleEnd)
                                    ? _hoverIndex! - _visibleStart
                                    : null,
                            onHoverChanged: (index) {
                              if (index == null) {
                                if (_hoverIndex != null) {
                                  setState(() => _hoverIndex = null);
                                }
                                return;
                              }
                              final actualIndex = _visibleStart + index;
                              if (_hoverIndex != actualIndex) {
                                setState(() => _hoverIndex = actualIndex);
                              }
                            },
                            onPanShift: (delta) {
                              if (delta.abs() >= 6) {
                                _shiftWindow(delta < 0 ? 4 : -4, candles.length);
                              }
                            },
                            onScaleChanged: (scaleDelta) {
                              if (scaleDelta > 1.05) {
                                _zoom(true, candles.length);
                              } else if (scaleDelta < 0.95) {
                                _zoom(false, candles.length);
                              }
                            },
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                _StatsGrid(candles: candles),
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Latest candles', style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 12),
                        ...candles.reversed.take(8).map(
                              (candle) => Padding(
                                padding: const EdgeInsets.only(bottom: 8),
                                child: Row(
                                  children: [
                                    Expanded(child: Text(DateFormat('HH:mm').format(candle.time))),
                                    Expanded(child: Text('O ${candle.open.toStringAsFixed(4)}')),
                                    Expanded(child: Text('H ${candle.high.toStringAsFixed(4)}')),
                                    Expanded(child: Text('L ${candle.low.toStringAsFixed(4)}')),
                                    Expanded(child: Text('C ${candle.close.toStringAsFixed(4)}')),
                                  ],
                                ),
                              ),
                            ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _StatsGrid extends StatelessWidget {
  const _StatsGrid({required this.candles});

  final List<MarketCandle> candles;

  @override
  Widget build(BuildContext context) {
    final high = candles.map((c) => c.high).reduce((a, b) => a > b ? a : b);
    final low = candles.map((c) => c.low).reduce((a, b) => a < b ? a : b);
    final volume = candles.fold<double>(0, (sum, candle) => sum + candle.volume);
    final open = candles.first.open;
    final close = candles.last.close;
    final ema20 = _ChartMath.ema(candles.map((c) => c.close).toList(), 20).last;
    final isCompact = MediaQuery.sizeOf(context).width < 420;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: isCompact ? 2.2 : 2.8,
          children: [
            _StatItem(label: 'Open', value: open.toStringAsFixed(4)),
            _StatItem(label: 'Close', value: close.toStringAsFixed(4)),
            _StatItem(label: 'High', value: high.toStringAsFixed(4)),
            _StatItem(label: 'Low', value: low.toStringAsFixed(4)),
            _StatItem(label: 'Volume', value: volume.toStringAsFixed(2)),
            _StatItem(label: 'EMA 20', value: ema20.toStringAsFixed(4)),
          ],
        ),
      ),
    );
  }
}

class _StatItem extends StatelessWidget {
  const _StatItem({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final isCompact = MediaQuery.sizeOf(context).width < 420;
    return Container(
      padding: EdgeInsets.all(isCompact ? 10 : 12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: isCompact ? 10 : 12, color: Colors.white54),
          ),
          SizedBox(height: isCompact ? 2 : 4),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              value,
              maxLines: 1,
              style: TextStyle(fontSize: isCompact ? 12 : 14, fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChartPanel extends StatelessWidget {
  const _ChartPanel({
    required this.candles,
    required this.hoveredIndex,
    required this.onHoverChanged,
    required this.onPanShift,
    required this.onScaleChanged,
  });

  final List<MarketCandle> candles;
  final int? hoveredIndex;
  final ValueChanged<int?> onHoverChanged;
  final ValueChanged<int> onPanShift;
  final ValueChanged<double> onScaleChanged;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final layout = _ChartLayout(
          width: constraints.maxWidth,
          height: constraints.maxHeight,
          candleCount: candles.length,
        );
        return MouseRegion(
          onHover: (event) =>
              onHoverChanged(_ChartMath.indexForPosition(event.localPosition, candles.length, constraints.maxWidth)),
          onExit: (_) => onHoverChanged(null),
          child: GestureDetector(
            onTapUp: (details) =>
                onHoverChanged(_ChartMath.indexForPosition(details.localPosition, candles.length, constraints.maxWidth)),
            onScaleUpdate: (details) {
              onHoverChanged(_ChartMath.indexForPosition(details.focalPoint, candles.length, constraints.maxWidth));
              onPanShift(details.focalPointDelta.dx.toInt());
              onScaleChanged(details.scale);
            },
            child: Stack(
              children: [
                CustomPaint(
                  painter: _CandlestickPainter(
                    candles: candles,
                    hoveredIndex: hoveredIndex,
                  ),
                  size: Size(constraints.maxWidth, constraints.maxHeight),
                ),
                if (hoveredIndex != null && hoveredIndex! >= 0 && hoveredIndex! < candles.length)
                  Positioned(
                    left: layout.tooltipLeft(hoveredIndex!),
                    top: layout.tooltipTop(candles[hoveredIndex!]),
                    child: _FloatingHoverInfoCard(candle: candles[hoveredIndex!]),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _ChartLayout {
  _ChartLayout({
    required this.width,
    required this.height,
    required this.candleCount,
  });

  final double width;
  final double height;
  final int candleCount;

  double get chartWidth => width - 72.0;
  double get chartHeight => height * 0.72;
  double get volumeHeight => height * 0.18;
  double get topPadding => 18.0;

  double xForIndex(int index) {
    final step = chartWidth / candleCount;
    return step * index + step / 2;
  }

  double yForPrice(double price, double low, double range) {
    return _ChartMath.priceToY(price, low, range, chartHeight, topPadding);
  }

  double tooltipLeft(int index) {
    final x = xForIndex(index);
    final desired = x + 16;
    final maxLeft = math.max(8.0, chartWidth - 190);
    return desired > maxLeft ? math.max(8.0, x - 196) : desired;
  }

  double tooltipTop(MarketCandle candle, {double? low, double? range}) {
    final actualLow = low ?? candle.low;
    final actualRange = range ?? ((candle.high - candle.low).abs().clamp(0.000001, double.infinity));
    final closeY = yForPrice(candle.close, actualLow, actualRange);
    return math.max(8.0, math.min(closeY - 92, chartHeight - 168));
  }
}

class _CandlestickPainter extends CustomPainter {
  _CandlestickPainter({
    required this.candles,
    required this.hoveredIndex,
  });

  final List<MarketCandle> candles;
  final int? hoveredIndex;

  @override
  void paint(Canvas canvas, Size size) {
    if (candles.isEmpty) return;

    const rightAxisWidth = 72.0;
    final chartWidth = size.width - rightAxisWidth;
    final chartHeight = size.height * 0.72;
    final volumeHeight = size.height * 0.18;
    final topPadding = 18.0;
    final step = chartWidth / candles.length;
    final bodyWidth = (step * 0.52).clamp(2.0, 18.0);

    final high = candles.map((c) => c.high).reduce(math.max);
    final low = candles.map((c) => c.low).reduce(math.min);
    final range = (high - low).abs().clamp(0.000001, double.infinity);
    final volumeMax = candles.map((c) => c.volume).fold<double>(0, math.max).clamp(1.0, double.infinity);

    final gridPaint = Paint()
      ..color = Colors.white12
      ..strokeWidth = 1;
    final risePaint = Paint()
      ..color = const Color(0xFF1FE36D)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;
    final fallPaint = Paint()
      ..color = const Color(0xFFFF5A7A)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;
    final riseFill = Paint()..color = const Color(0xFF1FE36D).withValues(alpha: 0.28);
    final fallFill = Paint()..color = const Color(0xFFFF5A7A).withValues(alpha: 0.28);
    final volumePaint = Paint()..color = const Color(0xFF5F8CFF).withValues(alpha: 0.35);

    for (var i = 1; i < 4; i++) {
      final y = chartHeight * i / 4;
      canvas.drawLine(Offset(0, y), Offset(chartWidth, y), gridPaint);
    }

    _drawMovingAverage(canvas, candles, low, range, chartHeight, topPadding, chartWidth, _ChartMath.ema(candles.map((c) => c.close).toList(), 20), const Color(0xFF4D9FFF));
    _drawMovingAverage(canvas, candles, low, range, chartHeight, topPadding, chartWidth, _ChartMath.ema(candles.map((c) => c.close).toList(), 50), const Color(0xFFFFB84D));

    for (var i = 0; i < candles.length; i++) {
      final candle = candles[i];
      final x = step * i + step / 2;
      final openY = _ChartMath.priceToY(candle.open, low, range, chartHeight, topPadding);
      final closeY = _ChartMath.priceToY(candle.close, low, range, chartHeight, topPadding);
      final highY = _ChartMath.priceToY(candle.high, low, range, chartHeight, topPadding);
      final lowY = _ChartMath.priceToY(candle.low, low, range, chartHeight, topPadding);
      final isUp = candle.close >= candle.open;
      final wickPaint = isUp ? risePaint : fallPaint;
      final fillPaint = isUp ? riseFill : fallFill;
      final isHovered = hoveredIndex == i;
      final body = Rect.fromLTRB(
        x - bodyWidth / 2,
        math.min(openY, closeY),
        x + bodyWidth / 2,
        math.max(openY, closeY),
      );

      final volumeBarHeight = (candle.volume / volumeMax) * volumeHeight;
      final volumeTop = chartHeight + (volumeHeight - volumeBarHeight);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x - bodyWidth / 2, volumeTop, bodyWidth, volumeBarHeight),
          const Radius.circular(2),
        ),
        volumePaint,
      );

      canvas.drawLine(
        Offset(x, highY),
        Offset(x, lowY),
        Paint()
          ..color = isHovered ? Colors.white : wickPaint.color
          ..strokeWidth = isHovered ? 2.2 : 1.5
          ..style = PaintingStyle.stroke,
      );

      canvas.drawRRect(
        RRect.fromRectAndRadius(body, const Radius.circular(2)),
        fillPaint,
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(body, const Radius.circular(2)),
        Paint()
          ..color = isHovered ? Colors.white : wickPaint.color
          ..strokeWidth = isHovered ? 1.6 : 1.0
          ..style = PaintingStyle.stroke,
      );

      if (isHovered) {
        final glow = Paint()
          ..color = (isUp ? const Color(0xFF1FE36D) : const Color(0xFFFF5A7A)).withValues(alpha: 0.16)
          ..style = PaintingStyle.fill;
        canvas.drawCircle(Offset(x, (openY + closeY) / 2), bodyWidth * 1.35, glow);

        canvas.drawLine(Offset(x, 0), Offset(x, chartHeight), Paint()..color = Colors.white24..strokeWidth = 1);
        canvas.drawLine(Offset(0, closeY), Offset(chartWidth, closeY), Paint()..color = Colors.white24..strokeWidth = 1);

        final labelPainter = TextPainter(
          text: TextSpan(
            text: candle.close.toStringAsFixed(4),
            style: const TextStyle(color: Colors.black, fontWeight: FontWeight.w800, fontSize: 11),
          ),
          textDirection: ui.TextDirection.ltr,
        )..layout();
        final labelWidth = labelPainter.width + 12;
        final labelHeight = labelPainter.height + 8;
        final labelY = closeY - labelHeight / 2;
        final labelRect = Rect.fromLTWH(chartWidth + 4, labelY, labelWidth, labelHeight);
        canvas.drawRRect(
          RRect.fromRectAndRadius(labelRect, const Radius.circular(8)),
          Paint()..color = isUp ? const Color(0xFF1FE36D) : const Color(0xFFFF5A7A),
        );
        labelPainter.paint(canvas, Offset(labelRect.left + 6, labelRect.top + 4));
      }
    }

    canvas.drawLine(Offset(chartWidth, 0), Offset(chartWidth, size.height), Paint()..color = Colors.white24..strokeWidth = 1);

    final priceLabels = <double>[high, low, (high + low) / 2, low + (range * 0.25), low + (range * 0.75)];
    for (final price in priceLabels) {
      final y = _ChartMath.priceToY(price, low, range, chartHeight, topPadding);
      final painter = TextPainter(
        text: TextSpan(
          text: price.toStringAsFixed(4),
          style: const TextStyle(color: Colors.white54, fontSize: 10),
        ),
        textDirection: ui.TextDirection.ltr,
      )..layout();
      painter.paint(canvas, Offset(chartWidth + 8, y - painter.height / 2));
      canvas.drawLine(Offset(chartWidth - 4, y), Offset(chartWidth, y), Paint()..color = Colors.white24..strokeWidth = 1);
    }

    final legend = TextPainter(
      text: const TextSpan(
        text: 'EMA20   EMA50   VOL',
        style: TextStyle(color: Colors.white54, fontSize: 11),
      ),
      textDirection: ui.TextDirection.ltr,
    )..layout();
    legend.paint(canvas, const Offset(8, 4));
    canvas.drawLine(const Offset(8, 20), const Offset(22, 20), Paint()..color = const Color(0xFF4D9FFF)..strokeWidth = 4);
    canvas.drawLine(const Offset(62, 20), const Offset(76, 20), Paint()..color = const Color(0xFFFFB84D)..strokeWidth = 4);
    canvas.drawLine(const Offset(121, 20), const Offset(135, 20), Paint()..color = const Color(0xFF5F8CFF).withValues(alpha: 0.35)..strokeWidth = 4);
  }

  void _drawMovingAverage(
    Canvas canvas,
    List<MarketCandle> candles,
    double low,
    double range,
    double chartHeight,
    double topPadding,
    double chartWidth,
    List<double> values,
    Color color,
  ) {
    if (values.isEmpty) return;
    final step = chartWidth / candles.length;
    final path = Path();
    for (var i = 0; i < values.length && i < candles.length; i++) {
      final x = step * i + step / 2;
      final y = _ChartMath.priceToY(values[i], low, range, chartHeight, topPadding);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant _CandlestickPainter oldDelegate) {
    return oldDelegate.candles != candles || oldDelegate.hoveredIndex != hoveredIndex;
  }
}

class _ChartMath {
  static int? indexForPosition(Offset position, int count, double width) {
    if (count <= 0 || width <= 0) return null;
    final step = width / count;
    final index = (position.dx / step).floor();
    if (index < 0 || index >= count) return null;
    return index;
  }

  static double priceToY(double price, double low, double range, double chartHeight, double topPadding) {
    return chartHeight - ((price - low) / range) * (chartHeight - topPadding - 6) - 6;
  }

  static List<double> ema(List<double> values, int period) {
    if (values.isEmpty) return const [];
    final result = <double>[];
    final k = 2 / (period + 1);
    var ema = values.first;
    for (final value in values) {
      ema = value * k + ema * (1 - k);
      result.add(ema);
    }
    return result;
  }
}

class _FloatingHoverInfoCard extends StatelessWidget {
  const _FloatingHoverInfoCard({required this.candle});

  final MarketCandle candle;

  @override
  Widget build(BuildContext context) {
    final change = candle.close - candle.open;
    final changePct = candle.open == 0 ? 0.0 : (change / candle.open) * 100;
    final range = candle.high - candle.low;
    final isUp = change >= 0;

    return Container(
      width: 182,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF151B27).withValues(alpha: 0.94),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white12),
        boxShadow: const [
          BoxShadow(color: Colors.black54, blurRadius: 18, offset: Offset(0, 10)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            DateFormat('HH:mm').format(candle.time),
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 12),
          ),
          const SizedBox(height: 10),
          _row('Open', candle.open.toStringAsFixed(4)),
          _row('High', candle.high.toStringAsFixed(4)),
          _row('Low', candle.low.toStringAsFixed(4)),
          _row('Close', candle.close.toStringAsFixed(4)),
          _row(
            'Chg',
            change.toStringAsFixed(4),
            valueColor: isUp ? const Color(0xFF1FE36D) : const Color(0xFFFF5A7A),
          ),
          _row(
            '%Chg',
            '${changePct.toStringAsFixed(2)}%',
            valueColor: isUp ? const Color(0xFF1FE36D) : const Color(0xFFFF5A7A),
          ),
          _row('Range', range.toStringAsFixed(4)),
          _row('Vol', candle.volume.toStringAsFixed(2)),
        ],
      ),
    );
  }

  Widget _row(String label, String value, {Color? valueColor}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.white70, fontSize: 11)),
          Text(value, style: TextStyle(color: valueColor ?? Colors.white, fontSize: 11, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}
