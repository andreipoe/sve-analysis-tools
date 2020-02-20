import pandas as pd
import plotly.graph_objects as ply

analyze = pd.read_pickle('data.pickle')
data  = stream[(stream.svewidth == 512) & (stream.version == 'arm19.2')]

labels = [
         "total", #0
         "loads", #1
         "stores", #2

         # Loads
         "non-sve", #3
         "sve", #4
         "contiguous", #5
         "all-lanes", #6
         "some-lanes", #7
         "gather", #8
         "all-lanes", #9
         "some-lanes", #10

         # Stores
         "non-sve", #11
         "sve", #12
         "contiguous", #13
         "all-lanes", #14
         "some-lanes", #15
         "scatter", #16
         "all-lanes", #17
         "some-lanes", #18
         ]
values = [
         data[data.type == 'load'].total.item(), #0-1
         data[data.type == 'store'].total.item(), #0-2

         data[data.type == 'load']['non-sve'].item(), #1-3
         data[data.type == 'load']['sve'].item(), #1-4
         data[data.type == 'load']['sve-contiguous'].item(), #4-5
         data[data.type == 'load']['sve-gather-scatter'].item(), #4-8
         data[data.type == 'load']['sve-contig-alllanes'].item(), #5-6
         data[data.type == 'load']['sve-contig-dislanes'].item(), #5-7
         data[data.type == 'load']['sve-gat-scat-alllanes'].item(), #8-9
         data[data.type == 'load']['sve-gat-scat-dislanes'].item(), #8-10

         data[data.type == 'store']['non-sve'].item(), #2-11
         data[data.type == 'store']['sve'].item(), #2-12
         data[data.type == 'store']['sve-contiguous'].item(), #12-13
         data[data.type == 'store']['sve-gather-scatter'].item(), #12-16
         data[data.type == 'store']['sve-contig-alllanes'].item(), #13-14
         data[data.type == 'store']['sve-contig-dislanes'].item(), #13-15
         data[data.type == 'store']['sve-gat-scat-alllanes'].item(), #16-17
         data[data.type == 'store']['sve-gat-scat-dislanes'].item(), #16-18
         ]

fig = ply.Figure(data=[ply.Sankey(
    node = dict(
      pad = 15,
      thickness = 20,
      line = { 'color': "black", 'width': 0.5 },
      label = labels,
      color = "lightblue"
    ),
    link = dict(
      source = [0, 0, 1, 1, 4, 4, 5, 5, 8,  8,    2,  2, 12, 12, 13, 13, 16, 16], # indices correspond to labels
      target = [1, 2, 3, 4, 5, 8, 6, 7, 9, 10,   11, 12, 13, 16, 14, 15, 17, 18],
      value = values
  ))
  ])

fig.update_layout(title_text=data.iloc[0].application, font_size=14).show()

