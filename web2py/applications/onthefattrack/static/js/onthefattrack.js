g_data = []
g_labels = []
g_tooltips = []
g_graph_id = ''
g_data_length = 0
g_weight_unit = 'lbs'

// Add array map
if (!Array.prototype.map)
{
  Array.prototype.map = function(fun /*, thisp*/)
  {
    var len = this.length;
    if (typeof fun != "function")
      throw new TypeError();

    var res = new Array(len);
    var thisp = arguments[1];
    for (var i = 0; i < len; i++)
    {
      if (i in this)
        res[i] = fun.call(thisp, this[i], i, this);
    }

    return res;
  };
}

// Add array clone
Array.prototype.clone = function() { return this.slice(0); }

function getGraph(id, data, tooltips, labels) {
    var change_labels = labels.map(function(val) { return '' });
    var label_length = labels.length;

    var even = (label_length % 2) == 0;
    var label_count = even ? 4 : 5;

    if (label_count < change_labels.length) {
        var indices = [];
        indices.push(0);

        if (even) {
            var mid = parseInt(Math.round(label_length / 2));
            var midmid = parseInt(Math.round(mid / 2));

            indices.push(midmid);
            indices.push(mid + midmid - 1);
        } else {
            var mid = parseInt(Math.round(label_length / 2)) - 1;
            var midmid = parseInt(Math.round(mid / 2));

            indices.push(midmid);
            indices.push(mid);
            indices.push(mid + midmid);
        }

        indices.push(label_length - 1);

        while (indices.length > 0) {
            var index = parseInt(Math.round(indices.shift()));
            change_labels[index] = labels[index];
        }

        labels = change_labels;
    }

    var line = new RGraph.Line(id, data);
    line.Set('chart.background.barcolor1', 'rgba(255,255,255,1)');
    line.Set('chart.background.barcolor2', 'rgba(255,255,255,1)');
    line.Set('chart.background.grid.color', 'rgba(238,238,238,1)');
    line.Set('chart.colors', ['rgba(122, 222, 244, 0.7)']);
    line.Set('chart.linewidth', 3);
    line.Set('chart.hmargin', 5);
    line.Set('chart.labels', labels);
    line.Set('chart.gutter', 60);

    line.Set('chart.tickmarks', 'dot');
    line.Set('chart.tickmarks.dot.color', 'blue');
    line.Set('chart.filled', false);
    line.Set('chart.fillstyle', '#daf1fa');
    line.Set('chart.tooltips', tooltips);
    line.Set('chart.crosshairs', true);
    line.Set('chart.title.xaxis', 'Date');
    line.Set('chart.title.yaxis', sprintf('Weight (%s)', g_weight_unit));
    line.Set('chart.shadow', true);

    line.Draw();
}

function updateGraph(id, new_weight, new_date, data, tooltips, labels) {
    g_data.push(new_weight);

    g_labels.push(new_date);

    tooltip = sprintf("%s: %0.1f %s", new_date, new_weight, g_weight_unit);

    g_tooltips.push(tooltip);

    if ($('#myLine').length) {
        // Clear the canvas and redraw the graph
        RGraph.Clear(document.getElementById('myLine'));
        getGraph('myLine', g_data, g_tooltips, g_labels);
    }
}
